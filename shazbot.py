#!/usr/bin/python

import asyncio
import discord
from discord.ext import commands
import pydle
import re
import shaz_db
import shaz_stats
import shaz_fastcap
from dotenv import load_dotenv
import os

load_dotenv()

# Configuration
IRC_SERVER = os.getenv("SHAZ_IRC_SERVER", None)
IRC_PORT = int(os.getenv("SHAZ_IRC_PORT", 6697))
IRC_CHANNEL = os.getenv("SHAZ_IRC_CHANNEL", "#READY")
IRC_NICK = os.getenv("SHAZ_IRC_NICK", "Shazbot")

DISCORD_TOKEN = os.getenv("SHAZ_DISCORD_TOKEN")

# Setting up the Discord bot with the necessary intents
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix='!', intents=intents)

ADMIN_USERS = { int(os.getenv("SHAZ_DISCORD_ADMIN_ID")) }
operators = set()

# Global variable to hold IRC bot reference
irc_bot = None
irc_response = ""  # Variable to store IRC responses

## watching ...
currently_watching = False
irc_watch_channel = None
discord_tv_channel = int(os.getenv("SHAZ_DEFAULT_DISCORD_TV"))

##fastcap
currently_fastcapping = False
irc_fastcap_channel = None
discord_fastcap_channel = int(os.getenv("SHAZ_DEFAULT_DISCORD_FASTCAP"))

# db
#TODO: consider that initialize_database() should accept either a variable number of arguments, or a list of queries to execute, to make it more modular
#      this is a cool idea in theory, but there would be a fair amount of extra work involved in practice methinks...
DB_NAME = os.getenv("SHAZ_DB_NAME", "game_log.db")
shaz_db.initialize_database(player_table_init=shaz_stats.PLAYER_TABLE_INIT, kills_log_table_init=shaz_stats.KILLS_LOG_TABLE_INIT, db_name=DB_NAME)
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
        await self.join(IRC_CHANNEL)

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

        global currently_fastcapping, irc_fastcap_channel, discord_fastcap_channel
        if currently_fastcapping and target == irc_fastcap_channel:
            # print("DEBUG: calling parse_single_cap...")
            async with db_lock:
                loop = asyncio.get_event_loop()
                fc_result = await loop.run_in_executor(None, shaz_fastcap.parse_single_cap, cleaned_message)
                if fc_result:
                    await send_message_to_channel(discord_fastcap_channel, "`" + fc_result + "`")

        global currently_watching, irc_watch_channel, discord_tv_channel

        if currently_watching and target == irc_watch_channel:
            # (alternatively could refactor shaz_db to be async as well)
            async with db_lock:
                await send_message_to_channel(discord_tv_channel, "`" + cleaned_message + "`")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, shaz_stats.parse_single_stat, cleaned_message)
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
    fc_access, fc_message = check_channel_access(discord_fastcap_channel)
    tv_access, tv_message = check_channel_access(discord_tv_channel)
    print(f"Fastcap channel ({discord_fastcap_channel}): {fc_message}")
    print(f"TV channel ({discord_tv_channel}): {tv_message}")

def is_admin_or_operator():
    async def predicate(ctx):
        return ctx.author.id in ADMIN_USERS or ctx.author.id in operators
    return commands.check(predicate)

@discord_bot.command(name='id')
@is_admin_or_operator()
async def get_discord_id(ctx):
    await ctx.send(f"Your user ID is: {ctx.author.id}")

@discord_bot.command(name='op')
async def add_operator(ctx, user_id: int):
    if ctx.author.id in ADMIN_USERS:
        operators.add(user_id)
        await ctx.send(f"User with ID {user_id} has been added as an operator.")
    else:
        await ctx.send("You don't have permission to add operators")

@discord_bot.command()
async def hello(ctx):
    """Responds with 'Hello!' when the command !hello is used."""
    await ctx.send('Hello!')

@discord_bot.command(name='list')
@is_admin_or_operator()
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
@is_admin_or_operator()
async def set_channel(ctx, channel_type: str, channel_id: int):
    global discord_tv_channel, discord_fastcap_channel

    channel_access, access_message = check_channel_access(channel_id)
    if (channel_access):
        # Handle channel type
        if channel_type.lower() == "tv":
            discord_tv_channel = channel_id
            await ctx.send(f"TV Discord channel set to {channel_id}")
            print(f"TV Discord channel set to {channel_id}")
        elif channel_type.lower() == "fastcap":
            discord_fastcap_channel = channel_id
            await ctx.send(f"Fastcap Discord channel set to {channel_id}")
            print(f"Fastcap Discord channel set to {channel_id}")
        else:
            await ctx.send(f"Unknown channel type: {channel_type}")
    else:
        await ctx.send(access_message)

# TODO: implement tracking & untracking (rather than misusing !watch :))
@discord_bot.command()
@is_admin_or_operator()
async def watch(ctx, channel_name: str):
    """
    Enables watching for a specified IRC channel.

    Args:
        ctx: The context of the command.
        channel_name (str): The name of the IRC channel to watch (e.g., #channelname or channelname).
    """
    global currently_watching, irc_watch_channel

    tv_access, tv_message = check_channel_access(discord_tv_channel)
    if tv_access == False:
        await ctx.send(f"Cannot !watch because of a problem with the the Discord TV channel:\n{tv_message}\nUse `!set_channel [channel_id]` to fix this.")
        return

    if not channel_name.startswith("#"):
        normalized_channel = f"#{channel_name}"
    else:
        normalized_channel = channel_name

    if irc_bot and irc_bot.connected:
        print(f"let's go!")

        # Set the global variables for watching state and channel
        currently_watching = True
        irc_watch_channel = normalized_channel
        #BUG: if the bot is already in the channel (eg: fastcapping), it won't
        #     give any indication that the !watch command was successful
        await irc_bot.join(irc_watch_channel)
        await ctx.send(f"Now watching IRC channel: {irc_watch_channel}")
        print(f"Started watching IRC channel: {irc_watch_channel}")
    else:
        await ctx.send("IRC bot is not connected to the server.")
        print("Failed to start watching: IRC bot not connected.")

@discord_bot.command()
@is_admin_or_operator()
async def fastcap(ctx, channel_name: str):
    """
    Sets an IRC channel to be the fastcap channel

    Args:
        ctx: The context of the command.
        channel_name (str): The name of the IRC channel to watch for fastcappin' (e.g., #channelname or channelname).
    """
    global currently_fastcapping, irc_fastcap_channel

    fc_access, fc_message = check_channel_access(discord_fastcap_channel)
    if fc_access == False:
        await ctx.send(f"Cannot !watch because of a problem with the the Discord TV channel:\n{fc_message}\nUse `!set_channel [channel_id]` to fix this.")
        return

    if not channel_name.startswith("#"):
        normalized_channel = f"#{channel_name}"
    else:
        normalized_channel = channel_name

    if irc_bot and irc_bot.connected:
        print(f"let's start fastcappin!")

        currently_fastcapping = True
        irc_fastcap_channel = normalized_channel
        #BUG: if the bot is already in the channel (eg: watching), it won't
        #     give any indication that the !fastcap command was successful

        await irc_bot.join(irc_fastcap_channel)
        await ctx.send(f"Now fastcappin' in IRC channel: {irc_fastcap_channel}")
        print(f"Started fastcappin' in IRC channel: {irc_fastcap_channel}")
    else:
        await ctx.send("IRC bot is not connected to the server.")
        print("Failed to start watching: IRC bot not connected.")

@discord_bot.command()
@is_admin_or_operator()
async def unwatch(ctx):
    """
    Disables watching for any IRC channel.
    
    Args:
        ctx: The context of the command.
    """
    global currently_watching, irc_watch_channel

    currently_watching = False
    irc_watch_channel = None
    await ctx.send("Stopped watching IRC channels.")
    print("Stopped watching IRC channels.")

@discord_bot.command(name='close')
@is_admin_or_operator()
async def close_db(ctx):
    shaz_db.close_db()
    await ctx.send("Closed database connection.")

#BUG TODO: this currently tramples the player's fastcap scores
@discord_bot.command(name='merge')
@is_admin_or_operator()
async def merge_players(ctx, source_id: int, target_id: int):
    source_name = shaz_db.get_player_name_by_id(source_id)
    target_name = shaz_db.get_player_name_by_id(target_id)
    if (source_name is None) or (target_name is None):
        await ctx.send("Sorry, one of those player IDs doesn't exist")
    else:
        shaz_db.merge_players(source_id, target_id)
        await ctx.send(f"Merged player ID {source_id} ({source_name}) into ID {target_id} ({target_name}).")

@discord_bot.command(name='whois')
@is_admin_or_operator()
async def whois_player(ctx, player_name: str):
    player_id = shaz_db.whois(player_name)
    response = f"No player found with a name similar to '{player_name}'."
    if player_id > 0:
        found_name = shaz_db.get_player_name_by_id(player_id)
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
    irc_color_code_regex = re.compile(r'\x03(\d{1,2}(,\d{1,2})?)?|\x02|\x1F|\x16|\x0F')
    cleaned_message = irc_color_code_regex.sub('', message)
    return cleaned_message


async def main():
    global irc_bot, IRC_NICK

    irc_bot = MyIRCBot(IRC_NICK)
    irc_task = asyncio.create_task(irc_bot.connect(IRC_SERVER, IRC_PORT, tls=True))

    discord_task = asyncio.create_task(discord_bot.start(DISCORD_TOKEN))

    # Wait for both the IRC and Discord bots to run concurrently
    await asyncio.gather(irc_task, discord_task)

asyncio.run(main())