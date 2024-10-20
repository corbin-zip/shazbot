#!/usr/bin/python

import sqlite3
import re
import sys

# TODO: probably swap these regexes to use \s+ instead of simply " "
#       (so it matches 1 or more spaces and therefore works with both IRC
#       and static logs without checks elsewhere in the code)
patterns = {
    # clocks
    #BUG: matches Team Storm, Team Inferno, and Team totals.
    #     i think the former 2 are fixable, the latter may not be by regex alone
    "two_player_clock": r"^\[\d{2}:\d{2}\] (?P<player>.+?) \.+.*?\s{2,} (?P<target>.+?) \.+.*$",
    "left_player_clock": r"^\[\d{2}:\d{2}\] (?P<player>.+?) \.+.*$",
    "right_player_clock": r"^\[\d{2}:\d{2}\] \s{3,} (?P<player>.+?) \.+.*$",

    # general
    "map_vote": r"^\[\d{2}:\d{2}\] (?P<player>.+?) initiated a map vote\.",
    #BUG: needs to better match these messages
    # <wow> [17:26]  twibes disconnected. 
    # <wow> [17:26]  twibes has disconnected.  Score:22  Kills:0 
    # (eg: i've seen it match player_name = "tribes has" action "disconnected")
    "connected": r"^\[\d{2}:\d{2}\] (?P<player>.+?) connected\.",
    "disconnected": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disconnected\.",
    "joined_team": r"^\[\d{2}:\d{2}\] (?P<player>.+?) joined team (?P<team_name>.+?)\.",
    "server_moved": r"^\[\d{2}:\d{2}\] SERVER moved (?P<player>.+?) to (?P<team_name>.+?)\.",
    # need to add "player has RECONNECTED"

    # random
    "flare_assist": r"^\[\d{2}:\d{2}\] (?P<player>.+?) provided a flare assist\.",
    "teamkilled": r"^\[\d{2}:\d{2}\] (?P<player>.+?) TEAMKILLED (?P<target>.+)\.",
    "defended_generator": r"^\[\d{2}:\d{2}\] (?P<player>.+?) defended a generator\.",

    # flag-related; deciding if/how i want to track team name
    "returned_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) returned the (?P<team>\w+) flag\.",
    "took_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) took the (?P<team>\w+) flag\.",
    "captured_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) captured the (?P<team>\w+) flag\.",
    "dropped_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) dropped the (?P<team>\w+) flag\.",
    "defended_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) defended the (?P<team>\w+) flag\.",
    "has_flag": r"^\[\d{2}:\d{2}\] (?P<player>.+?) has the (?P<team>\w+) flag\.",
    "killed_flag_carrier": r"^\[\d{2}:\d{2}\] (?P<player>.+?) killed the (?P<team>\w+) flag carrier\.",
    "defended_flag_carrier": r"^\[\d{2}:\d{2}\] (?P<player>.+?) defended the (?P<team>\w+) flag carrier\.",

    # destroying enemy neutrals
    "demolished_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) demolished a turret\.",
    "destroyed_enemy_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy turret\.",
    "destroyed_enemy_sensor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy sensor\.",
    "destroyed_enemy_remote_sensor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy remote sensor\.",
    "destroyed_enemy_remote_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy remote station\.",
    "destroyed_enemy_remote_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy remote turret\.",
    "destroyed_enemy_inventory_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy inventory station\.",
    "destroyed_enemy_generator": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy generator\.",
    "destroyed_enemy_fighter": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy fighter\.",
    "destroyed_enemy_bomber": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy bomber\.",
    "destroyed_enemy_transport": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy transport\.",
    "destroyed_enemy_vehicle_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy vehicle station\.",
    "destroyed_enemy_grav_cycle": r"^\[\d{2}:\d{2}\] (?P<player>.+?) destroyed an enemy grav cycle\.",

    # repair
    "repaired_vehicle_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired a vehicle station\.",
    "repaired_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired a turret\.",
    "repaired_generator": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired a generator\.",
    "repaired_inventory_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired an inventory station\.",
    "repaired_sensor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired a sensor\.",
    "repaired_remote_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) repaired a remote station\.",

    # disabled team stuff
    "disabled_team_remote_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team remote turret\.",
    "disabled_team_remote_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team remote station\.",
    "disabled_team_remote_sensor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team remote sensor\.",
    "disabled_team_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team turret\.",
    "disabled_team_inventory_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team inventory station\.",
    "disabled_team_generator": r"^\[\d{2}:\d{2}\] (?P<player>.+?) disabled a team generator\.",
    # disabled a team vehicle station?

    # deploying remote
    "deployed_remote_station": r"^\[\d{2}:\d{2}\] (?P<player>.+?) deployed a remote station\.",
    "deployed_remote_turret": r"^\[\d{2}:\d{2}\] (?P<player>.+?) deployed a remote turret\.",
    "deployed_remote_sensor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) deployed a remote sensor\.",
    "changed_turret_barrel": r"^\[\d{2}:\d{2}\] (?P<player>.+?) changed a base turret barrel\.",

    # player killing self
    "suicided": r"^\[\d{2}:\d{2}\] (?P<player>.+?) suicided\.",
    "killed_himself": r"^\[\d{2}:\d{2}\] (?P<player>.+?) killed himself\.",
    "killed_herself": r"^\[\d{2}:\d{2}\] (?P<player>.+?) killed herself\.",
    "tripped_his_own_mine": r"^\[\d{2}:\d{2}\] (?P<player>.+?) tripped his own mine\.",
    "tripped_her_own_mine": r"^\[\d{2}:\d{2}\] (?P<player>.+?) tripped her own mine\.",
    "will_respawn_shortly": r"^\[\d{2}:\d{2}\] (?P<player>.+?) will respawn shortly\.",
    "needs_armor": r"^\[\d{2}:\d{2}\] (?P<player>.+?) needs new armor\.",
    "landed_too_hard": r"^\[\d{2}:\d{2}\] (?P<player>.+?) landed too hard\.",
    "caught_blast": r"^\[\d{2}:\d{2}\] (?P<player>.+?) caught the blast\.",
    "became_spare_parts": r"^\[\d{2}:\d{2}\] (?P<player>.+?) became spare parts\.",

    # player killed by AI turrets
    "plasma_turret_fried": r"^\[\d{2}:\d{2}\] A plasma turret fried (?P<player>.+)\.",
    "aa_shot_down": r"^\[\d{2}:\d{2}\] An AA turret shot (?P<player>.+?) down\.",
    "sentry_turret_nailed": r"^\[\d{2}:\d{2}\] A sentry turret nailed (?P<player>.+)\.",
    "remote_turret_got": r"^\[\d{2}:\d{2}\] A remote turret got (?P<player>.+)\.",
    "mortar_turret_got": r"^\[\d{2}:\d{2}\] A mortar turret got (?P<player>.+)\.",
    "caught_mortar_shell": r"^\[\d{2}:\d{2}\] (?P<player>.+?) caught a mortar shell\.",
    "got_shot_down": r"^\[\d{2}:\d{2}\] (?P<player>.+?) got shot down\.",

    # player killing player
    # -with weapons
    "shot_down": r"^\[\d{2}:\d{2}\] (?P<player>.+?) shot (?P<target>.+?) down\.",
    "fried": r"^\[\d{2}:\d{2}\] (?P<player>.+?) fried (?P<target>.+)\.",
    "nailed": r"^\[\d{2}:\d{2}\] (?P<player>.+?) nailed (?P<target>.+)\.",
    "smoked": r"^\[\d{2}:\d{2}\] (?P<player>.+?) smoked (?P<target>.+)\.",
    "took_out": r"^\[\d{2}:\d{2}\] (?P<player>.+?) took out (?P<target>.+)\.",
    "eliminated": r"^\[\d{2}:\d{2}\] (?P<player>.+?) eliminated (?P<target>.+)\.",
    "gunned_down": r"^\[\d{2}:\d{2}\] (?P<player>.+?) gunned down (?P<target>.+)\.",
    "demolished": r"^\[\d{2}:\d{2}\] (?P<player>.+?) demolished (?P<target>.+)\.",
    "fed_plasma": r"^\[\d{2}:\d{2}\] (?P<target>.+?) ate (?P<player>.+)'s plasma\.",
    "defeated": r"^\[\d{2}:\d{2}\] (?P<player>.+?) defeated (?P<target>.+)\.",
    "tripped_mine": r"^\[\d{2}:\d{2}\] (?P<target>.+?) tripped (?P<player>.+?)'s mine\.",
    "detonated": r"^\[\d{2}:\d{2}\] (?P<player>.+?) detonated (?P<target>.+?)\.",
    "blasted": r"^\[\d{2}:\d{2}\] (?P<player>.+?) blasted (?P<target>.+)\.",
    "finished_off": r"^\[\d{2}:\d{2}\] (?P<player>.+?) finished off (?P<target>.+)\.",
    # -with vehicles; are there others?
    "bombed": r"^\[\d{2}:\d{2}\] (?P<player>.+?) bombed (?P<target>.+)\.",
    "mowed_down": r"^\[\d{2}:\d{2}\] (?P<player>.+?) mowed down (?P<target>.+)\.",
    # -with turret
    "turret_stopped": r"^\[\d{2}:\d{2}\] (?P<player>.+?)'s turret stopped (?P<target>.+)\.",

    # capture n hold
    "cnh_captured_objective": r"^\[\d{2}:\d{2}\] (?P<player>.+?) captured an objective for (?P<team>\w+)\.",
    "cnh_defended_objective": r"^\[\d{2}:\d{2}\] (?P<player>.+?) defended an objective\.",

    # score lists
    "score_list": r"^\[(?P<time>\d{2}:\d{2})\] +Scores -- Storm:(?P<storm_score>\d+) -- Inferno:(?P<inferno_score>\d+) -- (?P<map_name>.+)",

    # "hi" "oops" "shazbot!" etc - this matches all of them
    "player_message": r"^\[\d{2}:\d{2}\] (?P<player>.+?):\s+\"(?P<message>.+?)\""
}

# Parse a single line of text using the predefined patterns
def parse_line(line):
    for event, pattern in patterns.items():
        match = re.match(pattern, line)
        if match:
            return event, match.groupdict()
    return None, {}

# Create or connect to the SQLite database and set up the schema
def initialize_database(db_name="game_log.db"):
    conn = sqlite3.connect(db_name, check_same_thread=False)
    cursor = conn.cursor()

    # TODO: this *likely* doesn't include everything we want to track;
    #       need to verify that.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        total_kills INTEGER DEFAULT 0,
        total_deaths INTEGER DEFAULT 0,
        teamkills INTEGER DEFAULT 0,
        clocks INTEGER DEFAULT 0,

        flags_captured INTEGER DEFAULT 0,
        flags_returned INTEGER DEFAULT 0,

        suicided INTEGER DEFAULT 0,
        landed_too_hard INTEGER DEFAULT 0,
        needs_armor INTEGER DEFAULT 0,
        will_respawn_shortly INTEGER DEFAULT 0,
        killed_himself INTEGER DEFAULT 0,
        killed_herself INTEGER DEFAULT 0,
        tripped_his_own_mine INTEGER DEFAULT 0,
        tripped_her_own_mine INTEGER DEFAULT 0,
        became_spare_parts INTEGER DEFAULT 0,

        deployed_remote_sensor INTEGER DEFAULT 0,
        deployed_remote_station INTEGER DEFAULT 0,
        deployed_remote_turret INTEGER DEFAULT 0,

        disabled_inventory_stations INTEGER DEFAULT 0,
        disabled_team_remote_station INTEGER DEFAULT 0,
        disabled_team_remote_turret INTEGER DEFAULT 0,
        disabled_team_remote_sensor INTEGER DEFAULT 0,
        disabled_team_turret INTEGER DEFAULT 0,
        disabled_team_generator INTEGER DEFAULT 0,

        defended_generator INTEGER DEFAULT 0,
        defended_flag INTEGER DEFAULT 0,
        defended_flag_carrier INTEGER DEFAULT 0,

        cnh_captured_objective INTEGER DEFAULT 0,
        cnh_defended_objective INTEGER DEFAULT 0,

        repaired_turret INTEGER DEFAULT 0,
        repaired_generator INTEGER DEFAULT 0,
        repaired_sensor INTEGER DEFAULT 0,
        repaired_vehicle_station INTEGER DEFAULT 0,
        repaired_inventory_station INTEGER DEFAULT 0,
        repaired_remote_station INTEGER DEFAULT 0,

        got_shot_down INTEGER DEFAULT 0,
        aa_shot_down INTEGER DEFAULT 0,
        plasma_turret_fried INTEGER DEFAULT 0,
        remote_turret_got INTEGER DEFAULT 0,
        mortar_turret_got INTEGER DEFAULT 0,
        caught_mortar_shell INTEGER DEFAULT 0,
        sentry_turret_nailed INTEGER DEFAULT 0,

        demolished_turret INTEGER DEFAULT 0,
        destroyed_enemy_turret INTEGER DEFAULT 0,
        destroyed_enemy_sensor INTEGER DEFAULT 0,
        destroyed_enemy_remote_sensor INTEGER DEFAULT 0,
        destroyed_enemy_remote_station INTEGER DEFAULT 0,
        destroyed_enemy_remote_turret INTEGER DEFAULT 0,
        destroyed_enemy_inventory_station INTEGER DEFAULT 0,
        destroyed_enemy_generator INTEGER DEFAULT 0,
        destroyed_enemy_fighter INTEGER DEFAULT 0,
        destroyed_enemy_bomber INTEGER DEFAULT 0,
        destroyed_enemy_grav_cycle INTEGER DEFAULT 0,
        destroyed_enemy_transport INTEGER DEFAULT 0,
        destroyed_enemy_vehicle_station INTEGER DEFAULT 0,

        best_cap_avalon_storm INTEGER DEFAULT 180,
        best_cap_beggars_run_storm INTEGER DEFAULT 180,
        best_cap_damnation_storm INTEGER DEFAULT 180,
        best_cap_death_birds_fly_storm INTEGER DEFAULT 180,
        best_cap_desiccator_storm INTEGER DEFAULT 180,
        best_cap_firestorm_storm INTEGER DEFAULT 180,
        best_cap_katabatic_storm INTEGER DEFAULT 180,
        best_cap_paranoia_storm INTEGER DEFAULT 180,
        best_cap_quagmire_storm INTEGER DEFAULT 180,
        best_cap_recalescence_storm INTEGER DEFAULT 180,
        best_cap_reversion_storm INTEGER DEFAULT 180,
        best_cap_sanctuary_storm INTEGER DEFAULT 180,
        best_cap_slapdash_storm INTEGER DEFAULT 180,
        best_cap_thin_ice_storm INTEGER DEFAULT 180,
        best_cap_tombstone_storm INTEGER DEFAULT 180,

        best_cap_avalon_inferno INTEGER DEFAULT 180,
        best_cap_beggars_run_inferno INTEGER DEFAULT 180,
        best_cap_damnation_inferno INTEGER DEFAULT 180,
        best_cap_death_birds_fly_inferno INTEGER DEFAULT 180,
        best_cap_desiccator_inferno INTEGER DEFAULT 180,
        best_cap_firestorm_inferno INTEGER DEFAULT 180,
        best_cap_katabatic_inferno INTEGER DEFAULT 180,
        best_cap_paranoia_inferno INTEGER DEFAULT 180,
        best_cap_quagmire_inferno INTEGER DEFAULT 180,
        best_cap_recalescence_inferno INTEGER DEFAULT 180,
        best_cap_reversion_inferno INTEGER DEFAULT 180,
        best_cap_sanctuary_inferno INTEGER DEFAULT 180,
        best_cap_slapdash_inferno INTEGER DEFAULT 180,
        best_cap_thin_ice_inferno INTEGER DEFAULT 180,
        best_cap_tombstone_inferno INTEGER DEFAULT 180

    )
    """)

    # Create kills log table
    # TODO: can i specify the timezone?
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kills_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        killer_id INTEGER,
        victim_id INTEGER,
        event_type TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(killer_id) REFERENCES players(id),
        FOREIGN KEY(victim_id) REFERENCES players(id)
    )
    """)

    conn.commit()
    return conn

# Get player ID by name, create player if they don't exist
def get_or_create_player(conn, player_name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM players WHERE name = ?", (player_name,))
    row = cursor.fetchone()

    if row:
        return row[0]
    else:
        cursor.execute("INSERT INTO players (name) VALUES (?)", (player_name,))
        conn.commit()
        return cursor.lastrowid

# TODO: consider renaming to increment_player_stat
# TODO: consider removing value variable, as it may never be used
def update_player_stat(conn, player_id, column, value=1):
    cursor = conn.cursor()
    cursor.execute(f"UPDATE players SET {column} = {column} + ? WHERE id = ?", (value, player_id))
    conn.commit()

# Log kill events (including tripping mines, team kills, etc.)
def log_kill_event(conn, killer_id, victim_id, event_type):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO kills_log (killer_id, victim_id, event_type)
    VALUES (?, ?, ?)
    """, (killer_id, victim_id, event_type))
    conn.commit()

def handle_event(conn, event_type, data):
    # strip any leading or trailing spaces, which seems to happen occasionally in the IRC output
    # TODO: might not be necessary if we just fix the regex's to match 1 or more spaces after the time :)
    if 'player' in data and data['player'] is not None:
        player_name = data['player'].strip()
    if 'target' in data and data['target'] is not None:
        target_name = data['target'].strip()

    # player kills player
    # +1 kill to killer, +1 death to victim, log it
    if event_type in ["demolished", "smoked", "took_out", "eliminated", "shot_down", "bombed", "mowed_down", "finished_off", "defeated", "fed_plasma", "blasted", "turret_stopped", "gunned_down", "tripped_mine", "detonated"]:
        killer_id = get_or_create_player(conn, player_name)
        victim_id = get_or_create_player(conn, target_name)
        update_player_stat(conn, killer_id, "total_kills")
        update_player_stat(conn, victim_id, "total_deaths")
        log_kill_event(conn, killer_id, victim_id, event_type)

    # clocks
    elif event_type in ["left_player_clock", "right_player_clock", "two_player_clock"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, "clocks")
        if event_type == "two_player_clock":
            player2_id = get_or_create_player(conn, target_name)
            update_player_stat(conn, player2_id, "clocks")


    # special handlers for death by turret
    # because eg "An AA turret shot [player] down" can match "[player] shot [victim] down"
    # if turret: +1 death, +1 relevant stat
    # if player: +1 kill to killer, +1 death to victim, log it
    # TODO: after i fixed the space issue in parse_single_stat, i need to check if this is even a problem anymore
    elif event_type in ["fried", "shot_down", "nailed"]:
        if player_name == "A plasma turret":
            player_id = get_or_create_player(conn, target_name)
            update_player_stat(conn, player_id, "plasma_turret_fried")
            update_player_stat(conn, player_id, "total_deaths")
        elif player_name == "An AA turret":
            player_id = get_or_create_player(conn, target_name)
            update_player_stat(conn, player_id, "aa_shot_down")
            update_player_stat(conn, victim_id, "total_deaths")
        elif player_name == "A sentry turret":
            player_id = get_or_create_player(conn, target_name)
            update_player_stat(conn, player_id, "sentry_turret_nailed")
            update_player_stat(conn, player_id, "total_deaths")
        else:
            killer_id = get_or_create_player(conn, player_name)
            victim_id = get_or_create_player(conn, target_name)
            update_player_stat(conn, killer_id, "total_kills")
            update_player_stat(conn, victim_id, "total_deaths")
            log_kill_event(conn, killer_id, victim_id, event_type)
    
    # normal handlers for death by turret etc
    # +1 death, +1 relevant stat
    elif event_type in ["got_shot_down", "plasma_turret_fried", "aa_shot_down", "remote_turret_got", "mortar_turret_got", "caught_mortar_shell", "sentry_turret_nailed", "aa_shot_down"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, "total_deaths")
        update_player_stat(conn, player_id, event_type)

    # teamkilling
    # +1 teamkill to killer, +1 death to victim, log it
    elif event_type == "teamkilled":
        killer_id = get_or_create_player(conn, player_name)
        victim_id = get_or_create_player(conn, target_name)
        update_player_stat(conn, killer_id, "teamkills")
        update_player_stat(conn, victim_id, "total_deaths")
        log_kill_event(conn, killer_id, victim_id, event_type)

    # suicides
    # +1 death, +1 relevant stat
    elif event_type in ["suicided", "landed_too_hard", "needs_armor", "will_respawn_shortly", "killed_himself", "killed_herself", "tripped_his_own_mine", "tripped_her_own_mine", "became_spare_parts"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)
        update_player_stat(conn, player_id, "total_deaths")

    # flag captures
    # +1 flags_captured
    # TODO: do we want to count storm vs inferno, for example?
    elif event_type in ["captured_flag"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, "flags_captured")
    
    # flag returns
    # +1 flags_returned
    # TODO: do we want to count storm vs inferno, or example?
    elif event_type in ["returned_flag", "returned_storm_flag", "returned_inferno_flag"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, "flags_returned")

    # capture n hold
    elif event_type in ["cnh_captured_objective", "cnh_defended_objective"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

    # repairs
    elif event_type in ["repaired_turret", "repaired_generator", "repaired_inventory_station", "repaired_vehicle_station", "repaired_sensor"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

    # defended
    elif event_type in ["defended_generator", "defended_flag", "defended_flag_carrier"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

    # deployed remote
    elif event_type in ["deployed_remote_station", "deployed_remote_turret", "deployed_remote_sensor"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

    # disabled team's stuff (naughty!!)
    elif event_type in ["disabled_team_remote_station", "disabled_team_remote_turret", "disabled_team_remote_sensor", "disabled_team_turret", "disabled_team_generator"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

    # destroyed enemy base stuff
    elif event_type in ["destroyed_enemy_vehicle_station", "destroyed_enemy_turret", "destroyed_enemy_remote_turret", "destroyed_enemy_remote_sensor", "demolished_turret", "destroyed_enemy_remote_station", "destroyed_enemy_inventory_station", "destroyed_enemy_generator", "destroyed_enemy_sensor"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)
    
    # destroyed enemy vehicle
    elif event_type in ["destroyed_enemy_fighter", "destroyed_enemy_bomber", "destroyed_enemy_transport", "destroyed_enemy_grav_cycle"]:
        player_id = get_or_create_player(conn, player_name)
        update_player_stat(conn, player_id, event_type)

# TODO: consider breaking out the fast_cap stuff into a new file
# TODO: consider changing all _time variables to _time_remaining? is it too verbose?
cap_storm_last_grab_time = 0 # 60 minutes times 60 seconds = 3600 seconds
cap_storm_last_grab_name = None
cap_inferno_last_grab_time = 0 # 60 minutes times 60 seconds = 3600 seconds
cap_inferno_last_grab_name = None
cap_current_map = None

def extract_time_remaining(line):
    match = re.search(r'\[(\d+):(\d+)\]', line)
    if match:
        minutes, seconds = map(int, match.groups())
        return minutes * 60 + seconds
    return None

def parse_single_cap(conn, line, log_file="unmatched_cap_events.log"):
    # TODO: instead of "fixing" the line, i believe we can just fix the regex's to match up to 2 spaces
    fixed_line = re.sub(r"(\[\d{2}:\d{2}\])\s{2}", r"\1 ", line)
    current_time = extract_time_remaining(fixed_line)
    event_type, data = parse_line(fixed_line)
    if event_type and current_time is not None:
        # print("DEBUG: calling handle_cap_event...")
        cap_update = handle_cap_event(conn, event_type, data, current_time)
        return cap_update
    else:
        if re.match(r"^\[\d{2}:\d{2}\]", line):
            with open(log_file, "a") as file:
                file.write(f"{line}\n")

    return None


# TODO: consider extracting time from regex instead of passing it around
def handle_cap_event(conn, event_type, data, current_time):
    print(f"DEBUG: Event Type: {event_type}, Data: {data}, Current Time: {current_time}")

    # TODO: might not be necessary if we just fix the regex's to match 1 or more spaces after the time :)
    if 'player' in data and data['player'] is not None:
        player_name = data['player'].strip()
        # print(f"DEBUG: Player name: {player_name}")
    if 'team' in data and data['team'] is not None:
        team_name = data['team'].strip()
        # print(f"DEBUG: Team name: {team_name}")
    # TODO: i'm strip()'ing map_name so it should be ok, but i should really just fix the regex instead
    # example output (note the space after the name of the map):
    # DEBUG: Event Type: score_list, Data: {'time': '14:24', 'storm_score': '0', 'inferno_score': '0', 'map_name': 'Recalescence '}, Current Time: 864
    if 'map_name' in data and data['map_name'] is not None:
        map_name = data['map_name'].strip()
        # print(f"DEBUG: Map name: {map_name}")
    
    global cap_storm_last_grab_time, cap_storm_last_grab_name
    global cap_inferno_last_grab_time, cap_inferno_last_grab_name
    global cap_current_map

    # print(f"DEBUG: Storm Last Grab Time: {cap_storm_last_grab_time}, Inferno Last Grab Time: {cap_inferno_last_grab_time}")

    higher_grab_time = cap_inferno_last_grab_time
    if cap_storm_last_grab_time > cap_inferno_last_grab_time:
        higher_grab_time = cap_storm_last_grab_time

    # print(f"DEBUG: Higher Grab Time: {higher_grab_time}")

    #TODO: verify that there is no BUG here -- is it possible to move from eg a 20 minute game to a 60 minute?
    #      i don't think so.
    if current_time > higher_grab_time:
        print(f"DEBUG: Resetting game state (current_time ({current_time}) > higher_grab_time ({higher_grab_time})")
        cap_current_map = None
        cap_storm_last_grab_time = 3600
        cap_inferno_last_grab_time = 3600
        cap_storm_last_grab_name = None
        cap_inferno_last_grab_name = None
    
    if event_type == "score_list":
        print(f"DEBUG: Score List Event- current: '{cap_current_map}' new: '{map_name}'")
        return_string = None
        if cap_current_map != map_name:
            return_string = f"Now fastcappin' on {map_name}!"
        cap_current_map = map_name
        return return_string

    if event_type == "took_flag":
        if team_name == "Storm":
            cap_storm_last_grab_name = player_name
            cap_storm_last_grab_time = current_time
            # print(f"DEBUG: Storm Flag Grabbed: Player = {cap_storm_last_grab_name}, Time = {cap_storm_last_grab_time}")
        if team_name == "Inferno":
            cap_inferno_last_grab_name = player_name
            cap_inferno_last_grab_time = current_time
            # print(f"DEBUG: Inferno Took Flag: Player = {cap_inferno_last_grab_name}, Time = {cap_inferno_last_grab_time}")
    
    if event_type == "captured_flag":
        if cap_current_map is not None:
            if team_name == "Storm" and cap_storm_last_grab_name == player_name:
                cap_time = cap_storm_last_grab_time - current_time
                # print("---------------------------------------------------------------------------------------------")
                # print(f"!!!!!!!!!!!!! we have a cap to add for {player_name} on {cap_current_map} of time {cap_time}")
                # print("---------------------------------------------------------------------------------------------")
                cap_update = record_cap_time(conn, cap_storm_last_grab_name, cap_current_map, team_name, cap_time)
                cap_storm_last_grab_time = 3600
                cap_storm_last_grab_name = None
                return cap_update
            elif team_name == "Inferno" and cap_inferno_last_grab_name == player_name:
                cap_time = cap_inferno_last_grab_time - current_time
                # print("----------------------------------------------------------------------------------------------")
                # print(f"!!!!!!!!!!!!!! we have a cap to add for {player_name} on {cap_current_map} of time {cap_time}")
                # print("----------------------------------------------------------------------------------------------")
                cap_update = record_cap_time(conn, cap_inferno_last_grab_name, cap_current_map, team_name, cap_time)
                cap_inferno_last_grab_time = 3600
                cap_inferno_last_grab_name = None
                return cap_update
            else:
                return_string = f":( Most recent flag cap for {player_name} on {cap_current_map} ({team_name}) not counted; flag was likely dropped before being capped."
                print(return_string)
                return return_string
        else:
            return_string = f"!!!!!! BIG PROBLEM: we have a flag cap for {player_name} but we don't know what map we're on!!!!"
            print(return_string)
            return return_string
        
    if event_type == "dropped_flag":
        if team_name == "Storm":
            cap_storm_last_grab_name = None
            cap_storm_last_grab_time = 3600
        if team_name == "Inferno":
            cap_inferno_last_grab_name = None
            cap_inferno_last_grab_time = 3600
    return None


MAP_NAME_TO_COLUMN = {
    "Avalon": "best_cap_avalon",
    "Beggar's Run": "best_cap_beggars_run",
    "Damnation": "best_cap_damnation",
    "Death Birds Fly": "best_cap_death_birds_fly",
    "Desiccator": "best_cap_desiccator",
    "Firestorm": "best_cap_firestorm",
    "Katabatic": "best_cap_katabatic",
    "Paranoia": "best_cap_paranoia",
    "Quagmire": "best_cap_quagmire",
    "Recalescence": "best_cap_recalescence",
    "Reversion": "best_cap_reversion",
    "Sanctuary": "best_cap_sanctuary",
    "Slapdash": "best_cap_slapdash",
    "Thin Ice": "best_cap_thin_ice",
    "Tombstone": "best_cap_tombstone"
}

def record_cap_time(conn, player_name, map_name, flag_team, cap_time):
    return_string = None
    column = MAP_NAME_TO_COLUMN.get(map_name)
    
    if not column:
        return_string = f"Error: Unknown map '{map_name}'"
        print(return_string)
        return return_string

    if flag_team == "Storm":
        team_name = "Inferno"
    elif flag_team == "Inferno":
        team_name = "Storm"
    else:
        return_string = f"ERROR: :( There was a problem! Flag detected as belonging to '{flag_team}', which doesn't exist and should never happen"
        return return_string

    column = column + "_" + team_name.lower()

    player_id = get_or_create_player(conn, player_name)
    
    if player_id is None:
        return_string = f"Error: failed to lookup or create player '{player_name}'"
        print(return_string)
        return return_string
    
    cursor = conn.cursor()
    
    # query existing time
    cursor.execute(f"SELECT {column} FROM players WHERE id = ?", (player_id,))
    current_best = cursor.fetchone()

    # this error should never occur
    if current_best is None:
        return_string = f"Error: No record found for player {player_name} on map {map_name} ({team_name})"
        print(return_string)
        return return_string

    # compare existing time to new time
    if cap_time < current_best[0]:
        cursor.execute(f"UPDATE players SET {column} = ? WHERE id = ?", (cap_time, player_id))
        print(f"Updated {player_name}'s {map_name} ({team_name}) best cap time to {cap_time}.")
        return_string = f":) {player_name} (id {player_id}) set a new personal best on {map_name} ({team_name}) of {cap_time}s!"
    elif cap_time == current_best[0]:
        print(f"{player_name} tied their PB on {map_name} ({team_name}). Current PB is {current_best[0]}s.")
        return_string = f":| {player_name} (id {player_id}) captured the flag on {map_name} ({team_name}) in {cap_time}s, tying their personal best."
    else:
        print(f"{player_name}'s time for {map_name} ({team_name}) was not improved. Current PB is {current_best[0]}s.")
        return_string = f":| {player_name} (id {player_id}) captured the flag on {map_name} ({team_name}) in {cap_time}s, but failed to beat their personal best of {current_best[0]}s."
    
    conn.commit()
    return return_string

def parse_single_stat(conn, line, log_file="unmatched_stat_events.log"):
    # if there are 2 spaces between the time and the line, remove 1 of them
    # TODO: maybe remove this and just fix the regex's instead :)
    fixed_line = re.sub(r"(\[\d{2}:\d{2}\])\s{2}", r"\1 ", line)

    event_type, data = parse_line(fixed_line)
    if event_type:
        handle_event(conn, event_type, data)
    else:
        if re.match(r"^\[\d{2}:\d{2}\]", line):
            with open(log_file, "a") as file:
                file.write(f"{line}\n")

def whois(conn, player_name):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM players")
    players = cursor.fetchall()

    # Calculate similarity score and find the closest match
    closest_match_id, closest_score = -1, float("inf")
    for player_id, name in players:
        score = sum(1 for a, b in zip(player_name, name) if a != b) + abs(len(player_name) - len(name))
        if score < closest_score:
            closest_match_id, closest_score = player_id, score

    # Threshold for acceptable match
    if closest_score > len(player_name) * 0.5:  # Adjust threshold as necessary
        return -1
    return closest_match_id

def get_player_name_by_id(conn, player_id):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM players WHERE id = ?", (player_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# BUG TODO: merge function is broken for fastcap and will trample the player's scores
def merge_players(conn, source_id, target_id):
    cursor = conn.cursor()

    # Update all references of source_id in kills_log to target_id
    cursor.execute("UPDATE kills_log SET killer_id = ? WHERE killer_id = ?", (target_id, source_id))
    cursor.execute("UPDATE kills_log SET victim_id = ? WHERE victim_id = ?", (target_id, source_id))
    
    # Get all columns from players table except id and name
    cursor.execute("PRAGMA table_info(players)")
    columns = [info[1] for info in cursor.fetchall() if info[1] not in ["id", "name"]]

    # For each column, sum the stats from source to target
    for column in columns:
        cursor.execute(f"UPDATE players SET {column} = {column} + (SELECT {column} FROM players WHERE id = ?) WHERE id = ?", (source_id, target_id))

    # Delete the source player from players table
    cursor.execute("DELETE FROM players WHERE id = ?", (source_id,))

    conn.commit()

############# testing. comment this out when using shazbot.py instead ##################
# conn = initialize_database()

# if len(sys.argv) > 1:
#     argument = sys.argv[1]
#     with open(argument, "r") as log_file:
#         for line in log_file:
#             parse_single_stat(conn, line)
            
# conn.close()