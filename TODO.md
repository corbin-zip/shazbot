## bugs, todo's, etc

### bugs
* implement permissions!!!!
    - should have a central admin and individual "operators"
    - perhaps should implement granular control over which functions "ops" have access to?
    - marking this as a "bug" because it is essentially a massive security risk if any player can essentially [Majin Buu](https://www.youtube.com/watch?v=v3W2Y2NKIhE) (or [Walter White](https://old.reddit.com/r/breakingbad/comments/2dik2v/spoilera_little_detail_i_noticed_in_season_5/)) absorb stats from others
* `!merge` is broken
    - it hasn't been updated to deal with fastcap scores yet, so it'll simply sum them together instead of saving the lower number
* fix "IRC bot already in the IRC channel" bug
    - currently if you `!watch` and `!fastcap` the same channel, it will never execute the 2 lines after `irc_bot.join()`, which are to print to the console and send a message on Discord
    - there is currently no indication that the command was successful, but it appears to still function anyways
* fix `disconnected` regex
    - I've seen it match `player_name = "name here has"` with the action `disconnected` (rather than `player_name = "name here"`)
* verify `reconnected` regex
    - I'm just not sure if this works in all circumstances; it's probably broken in the same way that the `disconnected` messages are. It will probably be naturally caught in the `unmatched_[...].log` if it's a problem though.
* test or walk through potential fastcap timing bug
    - on line 498 I describe a potential bug that would occur if it was possible to change the length of the match while in the match
    - I think it *is* possible to change match length mid-match, but it would only apply to the *next* match
    - if the above assumption is true, does this matter?
    - still need to verify that the above assumption is true!
* fix `divider_line` and `score_header` regex's
    - what else to say? at the moment, they don't work!
    - their output will likely always be disregarded, but it's clogging up the logs
* fix clocks "Team Storm" "Team Inferno" "Team totals" bug
    - currently it's logging eg "Team Storm" as a player who is "clocking"
    - there are number of ways to fix this. do any of these ways allow a player to be named "Team Storm" for example?
        - if the answer is "yes" then, will other stats allow this or will those need to be fixed? can they be fixed?
        - if it's theoretically impossible for the script to ever be able to handle a player being named "Team Storm" (for example), then we shouldn't care about preserving that possibility with our fix here

### todo's
* implement a way for someone to register their Discord name with their name in the db
    - maybe operators would have this ability?
    - community small & trusting enough to probably allow `!register` for someone to pick a name, and then just prohibit others from `!register`'ing that same name
        - potential problem if someone changes their IGN and doesn't ask an operator to `!merge` it in time. but so what; what can a malicious actor do?
* implement a way to check stats & kill logs
    - if someone can register, they can write `!stats`. to check someone else, `!stats [playername]`. and if we decide to do some sort of leaderboard, maybe something like `!top kills`
    - website will allow for more in depth stuff like, show me all of the times this player has blown up an enemy with mines, or how many times this player has teamkilled this other player, etc
* implement a fastcap leaderboard
    - I'm thinking a traditional board that updates eg daily
    - perhaps the boards are stored in a new db that can be queried
    - maybe `!fastcap_leaderboard Avalon Storm` or `!fastcap_leaderboard All 10-20-23`
    - current & historical boards available on a website
        - site is generated dynamically eg via flask
        - or maybe site is static?
* triple-check `game_log.db` columns
    - are we tracking *everything* that we want to track? (we aren't! see next todo)
    - I think we're missing eg number of disconnects, reconnects, etc
    - maybe we have everything we care about *today*, but are we certain we won't care in the future?
* count storm vs inferno caps & returns
    - because it's fun! it doesn't really matter but it would be nice to have all of the stats from day 1
* look into `timestamp` in the `kills_log`
    - what timezone is it being tracked in?
    - does it make sense for it to be tracked in that timezone?
    - do we want to adjust it to a different timezone?
        - eg: adjust to UTC, and then adjust the output anytime we read data from `kills_log`?
        - or adjust to something "sane" like EST?
        - note: there does seem to be some EU players; they could be accomodated no matter what direction we chose, but maybe it makes sense to start and stick with UTC from the start & to be agnostic about time in the database?
* consider refactoring `update_player_stat`
    - if it's only ever going to increment a stat, then it should be named as such
    - if it's only ever going to increment by +1, then it doesn't need a `value` argument
* save/load the script's state
    - which IRC channels were being watched and their associated discord "TV" channels
    - which IRC channel was being tracked for fastcap
* fix tracking/untracking
    - currently `!watch` covers both but it's not supposed to. `!watch` and `!unwatch` should be independent of `!track` and `!untrack`
* fix regex's to account for 1 or 2 spaces after the time
    - currently there are a few places in the code where extra spaces are trimmed out, otherwise you end up with players named `' player name'`, for example
        - search for `fixed_line`
    - I believe this stems from static logs only having a **single space** between the time and the game message, whereas the live IRC logs have **two spaces**.
    - this will need to be thoroughly tested! as-is, I think it will break the `right_player_clock` regex if these additional `strip()`'s are removed, and possibly others.
* regex's that return `map_name`s are guilty of bad regex's as well
    - they will sometimes return something like `' Map Name'` and will be `strip()`'d
    - this is a todo rather than a bug because the code actually functions fine; I just feel like it's done in a lazy way
* check if regex workarounds in `handle_event()` are still necessary
    - now that there are regex's to match eg "An AA turret", must we check if the killer's name is "An AA turret"?
* apply format guidelines in README.md
    - constants are in ALL_UPPERCASE
    - globals are in SnakeCase
* implement a proper "debug" mode
    - rather than having debug print statements all over that are commented/not commented out, just write a `dprint()` function or something that checks for a `SHAZ_DEBUG` env variable
* declare types wherever possible

### to be considered
* think about tracking wins & losses
    - the last time I put much thought into this, it actually seemed rather difficult to do purely from an IRC perspective
    - ...but it's a more trivial problem if we have access to static logs
    - it seems like it could create more problems than it's worth if we track wins/losses *sometimes* but not other times, is the thing
* think about tracking some events separately
    - it would be really cool to say something like `!track #__SUNDAY 'Sunday Event 10-20-24'` and then when the event is over, `!untrack`, and then you could browse stats and the kill log from that specific event
    - really need to think about the best way to do this. a separate database for each event may make the most sense? maybe? but then giving totals could become cumbersome, since there are a *lot* of events throughout the year
    - there is probably a simple solution to this that I just haven't considered yet!
* think about breaking all of the fastcap stuff into a new file
    - are we planning on adding new game modes? if so, it may make sense to have each file as its own game mode
    - but then, should stats be its own file, and `shaz_db.py` is merely an interface for eg the stats or fastcap game modes to talk to the db indirectly?
    - I feel like these considerations don't matter as much right now, but may be worth considering if we add more features that touch the database
* rename `_time` variables to be more descriptive?
    - eg: `_time_remaining`
    - maybe I should've just done this when I wrote it down originally, it feels dumb to put on this list lol
* think about how `current_time` is used for fastcap stuff
    - currently it's being passed around as an argument
    - should it be pulled out of `data` via regex instead?
    - to be done correctly, I think this would mean updating all of the regex's
