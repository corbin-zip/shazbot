#!/usr/bin/python

import asyncio
import discord
from discord.ext import commands
import pydle
import re
import shaz_db
from dotenv import load_dotenv
import os

load_dotenv()

IRC_COLOR_CODE_REGEX = re.compile(r'\x03(\d{1,2}(,\d{1,2})?)?|\x02|\x1F|\x16|\x0F')

# Configuration
irc_server = os.getenv("SHAZ_IRC_SERVER", None)
irc_port = int(os.getenv("SHAZ_IRC_PORT", 6697))
irc_channel = os.getenv("SHAZ_IRC_CHANNEL", "#READY")
irc_nick = os.getenv("SHAZ_IRC_NICK", "Shazbot")

discord_token = os.getenv("SHAZ_DISCORD_TOKEN")

# Setting up the Discord bot with the necessary intents
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix='!', intents=intents)

# Global variable to hold IRC bot reference
irc_bot = None
irc_response = ""  # Variable to store IRC responses

## watching ...
watching = False
irc_watch_channel = None
discord_tv_channel = int(os.getenv("SHAZ_DEFAULT_DISCORD_TV"))

##fastcap
fast_tracking = False
irc_fc_channel = None
discord_fc_channel = int(os.getenv("SHAZ_DEFAULT_DISCORD_FASTCAP"))

# db
db_conn = shaz_db.initialize_database()
db_lock = asyncio.Lock()


# IRC ------------------------------------------------------------------------------------------
class MyIRCBot(pydle.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._channellist = set()
        self._list_event = asyncio.Event()  # event to signal when LIST command is complete

    async def on_connect(self):
        print("Connected to IRC server!")
        #TODO: rejoin any channels we need to be in, like watch channels or stat channels
        await self.join(irc_channel)

    async def get_channel_list(self) -> list:
        """Send the LIST command to the IRC server and collect the list of channels."""
        print("Sending LIST command to IRC server...")
        self._channellist.clear()
        self._list_event.clear()  # reset the event before starting the LIST command
        await self.rawmsg('LIST')

        print("Waiting for channel list to be populated...")
        await self._list_event.wait()  # Wait until on_raw_323 sets the event
        print(f"Channel list received: {self._channellist}")
        return list(self._channellist)

    async def on_raw_321(self, *args):
        """Handler for RPL_LISTSTART (321), which indicates the start of a channel list response."""
        print("Received 321: Channel list start.")
        self._channellist.clear()  # Clear existing channel list when a new LIST command starts.

    async def on_raw_322(self, message):
        """Handler for RPL_LIST (322), which provides details for each channel."""
        print(f"Received 322: {message}")
        try:
            # message.params contains information about the channel. Typically:
            # message.params[1] is the channel name.
            # message.params[2] is the number of users in the channel.
            # message.params[3] is the channel topic.
            channel_name = message.params[1]
            print(f"Adding channel to list: {channel_name}")
            self._channellist.add(channel_name)  # Add the channel name to the set
        except IndexError:
            print(f"Unexpected 322 message format: {message}")

    async def on_raw_323(self, *args):
        """Handler for RPL_LISTEND (323), which indicates the end of a channel list response."""
        print(f"Received 323: Channel list end. Total channels collected: {len(self._channellist)}")
        # Set the event to signal that the LIST response is complete.
        self._list_event.set()

    async def on_message(self, target, source, message):
        """
        Handles messages sent in IRC channels that the bot has joined.
        
        Args:
            target (str): The channel or target the message is sent to.
            source (str): The source user sending the message.
            message (str): The content of the message.
        """

        cleaned_message = strip_irc_formatting(message)

        # print(f"(dbg) Message from {source} in {target}: {message}")

        if message.strip().lower() == "!hello":
            await self.message(target, f"Hello, {source}!")

        global fast_tracking, irc_fc_channel, discord_fc_channel
        if fast_tracking and target == irc_fc_channel:
            # print("DEBUG: calling parse_single_cap...")
            async with db_lock:
                loop = asyncio.get_event_loop()
                fc_result = await loop.run_in_executor(None, shaz_db.parse_single_cap, db_conn, cleaned_message)
                if fc_result:
                    await send_message_to_channel(discord_fc_channel, "`" + fc_result + "`")

        global watching, irc_watch_channel, discord_tv_channel

        if watching and target == irc_watch_channel:
            # (alternatively could refactor shaz_db to be async as well)
            async with db_lock:
                await send_message_to_channel(discord_tv_channel, "`" + cleaned_message + "`")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shaz_db.parse_single_stat, db_conn, cleaned_message)
            # shaz_db.parse_single_stat(db_conn, cleaned_message)

        # if target in track_list...


# ------------------------------------------------------------------------
# ------------------------------------------------------------------------
# --- discord ------------------------------------------------------------
# ------------------------------------------------------------------------
# ------------------------------------------------------------------------

@discord_bot.event
async def on_ready():
    """Event handler for when the bot successfully connects to Discord."""
    print(f'Logged in as {discord_bot.user}')

    # verify access to both fc & tv channels; print debug error if there's a problem
    fc_access, fc_message = check_channel_access(discord_fc_channel)
    tv_access, tv_message = check_channel_access(discord_tv_channel)
    print(f"Fastcap channel ({discord_fc_channel}): {fc_message}")
    print(f"TV channel ({discord_tv_channel}): {tv_message}")

# TODO: implement tracking & untracking (rather than misusing !watch :))
@discord_bot.command()
async def hello(ctx):
    """Responds with 'Hello!' when the command !hello is used."""
    await ctx.send('Hello!')

@discord_bot.command(name='list')
async def list_channels(ctx):
    """Sends the IRC LIST command and mirrors the channel list output to the Discord channel."""
    global irc_response
    irc_response = ""  # Reset response before fetching new data

    if irc_bot and irc_bot.connected:
        print("Executing !list command...")
        channels = await irc_bot.get_channel_list()  # Get the list of channels
        print(f"Channels received in !list command: {channels}")

        # Join channels with newlines for Discord display
        irc_response = "\n".join(channels)
        await ctx.send(f"IRC Channel List:\n```\n{irc_response}\n```")
    else:
        await ctx.send("IRC bot is not connected to the server.")

def check_channel_access(channel_id: int) -> tuple[bool, str]:
    try:
        # Try to fetch the channel to verify bot access
        channel = discord_bot.get_channel(channel_id)

        if channel is None:
            return False, "Invalid channel ID"

        if channel.type != discord.ChannelType.text:
            print(f"channel #{channel.name} ({channel_id}) listed as type {channel.type} rather than text channel; unable to send messages to it")
            return False, f"Channel #{channel.name} ({channel_id}) isn't a text channel, so the bot cannot send messages to it"

        # Check if the bot has permission to send messages in the channel
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.send_messages:
            return False, f"Bot lacks permission to send messages in channel #{channel.name} ({channel_id})"
        return True, f"Channel #{channel.name} ({channel_id}) is valid and accessible by the Discord bot"

    except discord.Forbidden:
        return False, "The bot does not have permission to send messages in that channel."
    except Exception as e:
        return False, f"An error ocurred: {str(e)}"

@discord_bot.command()
async def set_channel(ctx, channel_type: str, channel_id: int):
    global discord_tv_channel, discord_fc_channel

    channel_access, access_message = check_channel_access(channel_id)
    if (channel_access):
        # Handle channel type
        if channel_type.lower() == "tv":
            discord_tv_channel = channel_id
            await ctx.send(f"TV Discord channel set to {channel_id}")
            print(f"TV Discord channel set to {channel_id}")
        elif channel_type.lower() == "fastcap":
            discord_fc_channel = channel_id
            await ctx.send(f"Fastcap Discord channel set to {channel_id}")
            print(f"Fastcap Discord channel set to {channel_id}")
        else:
            await ctx.send(f"Unknown channel type: {channel_type}")
    else:
        await ctx.send(access_message)


#TODO: verify that discord_tv_channel is OK before allowing !watch
@discord_bot.command()
async def watch(ctx, channel_name: str):
    """
    Enables watching for a specified IRC channel.

    Args:
        ctx: The context of the command.
        channel_name (str): The name of the IRC channel to watch (e.g., #channelname or channelname).
    """
    global watching, irc_watch_channel

    if not channel_name.startswith("#"):
        normalized_channel = f"#{channel_name}"
    else:
        normalized_channel = channel_name

    if irc_bot and irc_bot.connected:
        print(f"let's go!")

        # Set the global variables for watching state and channel
        watching = True
        irc_watch_channel = normalized_channel
        await irc_bot.join(irc_watch_channel)
        await ctx.send(f"Now watching IRC channel: {irc_watch_channel}")
        print(f"Started watching IRC channel: {irc_watch_channel}")
    else:
        await ctx.send("IRC bot is not connected to the server.")
        print("Failed to start watching: IRC bot not connected.")


#TODO: verify that discord_fc_channel is OK before allowing !fastcap
@discord_bot.command()
async def fastcap(ctx, channel_name: str):
    """
    Sets an IRC channel to be the fastcap channel

    Args:
        ctx: The context of the command.
        channel_name (str): The name of the IRC channel to watch for fastcappin' (e.g., #channelname or channelname).
    """
    global fast_tracking, irc_fc_channel

    if not channel_name.startswith("#"):
        normalized_channel = f"#{channel_name}"
    else:
        normalized_channel = channel_name

    if irc_bot and irc_bot.connected:
        print(f"let's start fastcappin!")

        fast_tracking = True
        irc_fc_channel = normalized_channel
        await irc_bot.join(irc_fc_channel)
        await ctx.send(f"Now fastcappin' in IRC channel: {irc_fc_channel}")
        print(f"Started fastcappin' in IRC channel: {irc_fc_channel}")
    else:
        await ctx.send("IRC bot is not connected to the server.")
        print("Failed to start watching: IRC bot not connected.")

@discord_bot.command()
async def unwatch(ctx):
    """
    Disables watching for any IRC channel.
    
    Args:
        ctx: The context of the command.
    """
    global watching, irc_watch_channel

    watching = False
    irc_watch_channel = None
    await ctx.send("Stopped watching IRC channels.")
    print("Stopped watching IRC channels.")

@discord_bot.command(name='close')
async def close_db(ctx):
    global db_conn
    db_conn.close()
    await ctx.send("Closed database connection.")

#BUG TODO: this currently tramples the player's fastcap scores
@discord_bot.command(name='merge')
async def merge_players(ctx, source_id: int, target_id: int):
    global db_conn
    source_name = shaz_db.get_player_name_by_id(db_conn, source_id)
    target_name = shaz_db.get_player_name_by_id(db_conn, target_id)
    if (source_name is None) or (target_name is None):
        await ctx.send("Sorry, one of those player IDs doesn't exist")
    else:
        shaz_db.merge_players(db_conn, source_id, target_id)
        await ctx.send(f"Merged player ID {source_id} ({source_name}) into ID {target_id} ({target_name}).")

@discord_bot.command(name='whois')
async def whois_player(ctx, player_name: str):
    global db_conn
    player_id = shaz_db.whois(db_conn, player_name)
    response = f"No player found with a name similar to '{player_name}'."
    if player_id > 0:
        found_name = shaz_db.get_player_name_by_id(db_conn, player_id)
        response = f"Closest match is player ID {player_id} ({found_name})."
    await ctx.send(response)

async def send_message_to_channel(channel_id: int, message: str):
    channel = discord_bot.get_channel(channel_id)
    if channel:
        await channel.send(message)
        # print(f"sent it to {channel_id}")
    else:
        print(f"id {channel_id} not found")

def strip_irc_formatting(message: str) -> str:
    """
    Strips IRC color codes and formatting characters from a message.
    
    Args:
        message (str): The IRC message with formatting codes.
        
    Returns:
        str: The cleaned message without color codes or formatting.
    """
    cleaned_message = IRC_COLOR_CODE_REGEX.sub('', message)
    return cleaned_message


async def main():
    global irc_bot, irc_nick

    irc_bot = MyIRCBot(irc_nick)
    irc_task = asyncio.create_task(irc_bot.connect(irc_server, irc_port, tls=True))

    discord_task = asyncio.create_task(discord_bot.start(discord_token))

    # Wait for both the IRC and Discord bots to run concurrently
    await asyncio.gather(irc_task, discord_task)

asyncio.run(main())