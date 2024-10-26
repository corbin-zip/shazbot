## changelog

### 10/26/24
* refactor; pass around db_conn
* `!watch` no longer tracks
* add `!track` and other tracking-related commands
* allow for tracking of multiple channels

### 10/24/24
* refactor; separate out stat tracking & fastcapping from db
* `shaz_db.py` is now the only file that interfaces directly with the db
* `shaz_fastcap.py` contains nearly all of the code required for fastcapping
* `update_player_stat()` is now `increment_player_stat()`

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