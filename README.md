# Danger!
Currently there is NO permissions checking. Anyone in any server that the Discord bot is connected to can send it commands!

# IYKYK
TODO: Write a summary here that makes to people outside of the [TAA Discord](https://discord.com/tribesaa)

# How to

TODO: Finish writing this.

## Environmental Variables (.env)

Create a file named `.env` and put something like this in there:
```sh
export SHAZ_DISCORD_TOKEN="discord token here"
export SHAZ_IRC_SERVER="irc.libera.chat"
export SHAZ_IRC_PORT="6697"
export SHAZ_IRC_NICK="Shazbot"
export SHAZ_IRC_CHANNEL="#shazready"
export SHAZ_DEFAULT_DISCORD_TV="discord_channel_id"
export SHAZ_DEFAULT_DISCORD_FASTCAP="discord_channel_id"
```
You can get channel IDs from Discord by enabling dev mode in your client and right-clicking on a channel and selecting "get channel ID"

# Style guide

From [here](http://www.oualline.com/style/c03.html), I like "System C" for variable and function names. That is:

|   Example   | When to use | Description |
| ----------- | ----------- | ----------- |
| total_count | Local variable and function names | All lowercase words separated by underscores |
| TotalCount  | Global variables and functions | Uppercase and lowercase with no separators |
| NAME_MAX    | Constants | All uppercase words separated by underscores |

...that said, I'm not following this convention nearly at all right now, and I need to go back through and fix it up! :) I just figured it would be a good idea to pick a style guide before making my first git commit.

