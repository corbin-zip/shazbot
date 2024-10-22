## changelog

### 10/22/24
* remove style guide; changed my mind about the style
* more consistently apply style (eg `CONSTANT_VARIABLES` and `anything_else`)
* add changelog :)

### 10/21/24
* add rudimentary permissions (via `SHAZ_DISCORD_ADMIN_ID` in `.env`)

### 10/20/24
* `TODO.md` add bug & todo lists 
* match some additional `EVENT_PATTERNS`
* log unmatched events to help us track down any more that are missing
* verify that the discord bot can send messages to the channels it's being asked to & that the channel is a text channel
* display warning in the console on first connect if the bot can't message the channels specified in `.env`