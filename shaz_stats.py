import shaz_db
import re

PLAYER_TABLE_INIT = """
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
"""

# TODO: can i specify the timezone?
KILLS_LOG_TABLE_INIT = """
    CREATE TABLE IF NOT EXISTS kills_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        killer_id INTEGER,
        victim_id INTEGER,
        event_type TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(killer_id) REFERENCES players(id),
        FOREIGN KEY(victim_id) REFERENCES players(id)
    )
"""

# TODO: probably swap these regexes to use \s+ instead of simply " "
#       (so it matches 1 or more spaces and therefore works with both IRC
#       and static logs without checks elsewhere in the code)
EVENT_PATTERNS = {
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
    "reconnected": r"^\[\d{2}:\d{2}\] (?P<player>.+?) has RECONNECTED\. +Score:(?P<score>\d+) +Kills:(?P<kills>\d+)$",
    # BUG: verify reconnected; does it work with/without scores/kills?
    #      it's probably broken in the same way that disconnected is

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

    # throw away
    "flags_secure": r"^\[\d{2}:\d{2}\] Both team's flags are secure\.",
    "team_scores": r"^\[\d{2}:\d{2}\] Team (?P<team>\w+) scores\!",
    "switched_team": r"^\[\d{2}:\d{2}\] (?P<player>.+?) switched to team (?P<team_name>.+?)\.",
    #BUG: these 2 don't match:
    "divider_line": r"^\[\d{2}:\d{2}\] {2,}[-]{32} {3,}[-]{32}$",
    "score_header": r"^\[\d{2}:\d{2}\] {2,}Warrior Name {5,}Score Kills TKs {3,}Warrior Name {5,}Score Kills TKs$",

    # "hi" "oops" "shazbot!" etc - this matches all of them
    "player_message": r"^\[\d{2}:\d{2}\] (?P<player>.+?):\s+\"(?P<message>.+?)\""
    
}





def handle_stat_event(db_conn, event_type, data):
    # strip any leading or trailing spaces, which seems to happen occasionally in the IRC output
    # TODO: might not be necessary if we just fix the regex's to match 1 or more spaces after the time :)
    if 'player' in data and data['player'] is not None:
        player_name = data['player'].strip()
    if 'target' in data and data['target'] is not None:
        target_name = data['target'].strip()

    # player kills player
    # +1 kill to killer, +1 death to victim, log it
    if event_type in ["demolished", "smoked", "took_out", "eliminated", "shot_down", "bombed", "mowed_down", "finished_off", "defeated", "fed_plasma", "blasted", "turret_stopped", "gunned_down", "tripped_mine", "detonated"]:
        killer_id = shaz_db.get_or_create_player(db_conn, player_name)
        victim_id = shaz_db.get_or_create_player(db_conn, target_name)
        increment_player_stat(db_conn, killer_id, "total_kills")
        increment_player_stat(db_conn, victim_id, "total_deaths")
        log_kill_event(db_conn, killer_id, victim_id, event_type)

    # clocks
    elif event_type in ["left_player_clock", "right_player_clock", "two_player_clock"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, "clocks")
        if event_type == "two_player_clock":
            player2_id = shaz_db.get_or_create_player(db_conn, target_name)
            increment_player_stat(db_conn, player2_id, "clocks")


    # special handlers for death by turret
    # because eg "An AA turret shot [player] down" can match "[player] shot [victim] down"
    # if turret: +1 death, +1 relevant stat
    # if player: +1 kill to killer, +1 death to victim, log it
    # TODO: after i fixed the space issue in parse_single_stat, i need to check if this is even a problem anymore
    elif event_type in ["fried", "shot_down", "nailed"]:
        if player_name == "A plasma turret":
            player_id = shaz_db.get_or_create_player(db_conn, target_name)
            increment_player_stat(db_conn, player_id, "plasma_turret_fried")
            increment_player_stat(db_conn, player_id, "total_deaths")
        elif player_name == "An AA turret":
            player_id = shaz_db.get_or_create_player(db_conn, target_name)
            increment_player_stat(db_conn, player_id, "aa_shot_down")
            increment_player_stat(db_conn, victim_id, "total_deaths")
        elif player_name == "A sentry turret":
            player_id = shaz_db.get_or_create_player(db_conn, target_name)
            increment_player_stat(db_conn, player_id, "sentry_turret_nailed")
            increment_player_stat(db_conn, player_id, "total_deaths")
        else:
            killer_id = shaz_db.get_or_create_player(db_conn, player_name)
            victim_id = shaz_db.get_or_create_player(db_conn, target_name)
            increment_player_stat(db_conn, killer_id, "total_kills")
            increment_player_stat(db_conn, victim_id, "total_deaths")
            log_kill_event(db_conn, killer_id, victim_id, event_type)
    
    # normal handlers for death by turret etc
    # +1 death, +1 relevant stat
    elif event_type in ["got_shot_down", "plasma_turret_fried", "aa_shot_down", "remote_turret_got", "mortar_turret_got", "caught_mortar_shell", "sentry_turret_nailed", "aa_shot_down"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, "total_deaths")
        increment_player_stat(db_conn, player_id, event_type)

    # teamkilling
    # +1 teamkill to killer, +1 death to victim, log it
    elif event_type == "teamkilled":
        killer_id = shaz_db.get_or_create_player(db_conn, player_name)
        victim_id = shaz_db.get_or_create_player(db_conn, target_name)
        increment_player_stat(db_conn, killer_id, "teamkills")
        increment_player_stat(db_conn, victim_id, "total_deaths")
        log_kill_event(db_conn, killer_id, victim_id, event_type)

    # suicides
    # +1 death, +1 relevant stat
    elif event_type in ["suicided", "landed_too_hard", "needs_armor", "will_respawn_shortly", "killed_himself", "killed_herself", "tripped_his_own_mine", "tripped_her_own_mine", "became_spare_parts"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)
        increment_player_stat(db_conn, player_id, "total_deaths")

    # flag captures
    # +1 flags_captured
    # TODO: do we want to count storm vs inferno, for example?
    elif event_type in ["captured_flag"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, "flags_captured")
    
    # flag returns
    # +1 flags_returned
    # TODO: do we want to count storm vs inferno, or example?
    elif event_type in ["returned_flag", "returned_storm_flag", "returned_inferno_flag"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, "flags_returned")

    # capture n hold
    elif event_type in ["cnh_captured_objective", "cnh_defended_objective"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)

    # repairs
    elif event_type in ["repaired_turret", "repaired_generator", "repaired_inventory_station", "repaired_vehicle_station", "repaired_sensor"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)

    # defended
    elif event_type in ["defended_generator", "defended_flag", "defended_flag_carrier"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)

    # deployed remote
    elif event_type in ["deployed_remote_station", "deployed_remote_turret", "deployed_remote_sensor"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)

    # disabled team's stuff (naughty!!)
    elif event_type in ["disabled_team_remote_station", "disabled_team_remote_turret", "disabled_team_remote_sensor", "disabled_team_turret", "disabled_team_generator"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)

    # destroyed enemy base stuff
    elif event_type in ["destroyed_enemy_vehicle_station", "destroyed_enemy_turret", "destroyed_enemy_remote_turret", "destroyed_enemy_remote_sensor", "demolished_turret", "destroyed_enemy_remote_station", "destroyed_enemy_inventory_station", "destroyed_enemy_generator", "destroyed_enemy_sensor"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)
    
    # destroyed enemy vehicle
    elif event_type in ["destroyed_enemy_fighter", "destroyed_enemy_bomber", "destroyed_enemy_transport", "destroyed_enemy_grav_cycle"]:
        player_id = shaz_db.get_or_create_player(db_conn, player_name)
        increment_player_stat(db_conn, player_id, event_type)


def parse_single_stat(db_conn, line, log_file="unmatched_stat_events.log"):
    # if there are 2 spaces between the time and the line, remove 1 of them
    # TODO: maybe remove this and just fix the regex's instead :)
    fixed_line = re.sub(r"(\[\d{2}:\d{2}\])\s{2}", r"\1 ", line)

    for event, pattern in EVENT_PATTERNS.items():
        match = re.match(pattern, fixed_line)
        if match:
            handle_stat_event(db_conn, event, match.groupdict())
        else:
            if re.match(r"^\[\d{2}:\d{2}\]", line):
                with open(log_file, "a") as file:
                    file.write(f"{line}\n")

def increment_player_stat(db_conn, player_id, stat_column):
    shaz_db.exec_query(db_conn, f"UPDATE players SET {stat_column} = {stat_column} + 1 WHERE id = ?", (player_id,))

# Log kill events (including tripping mines, team kills, etc.)
def log_kill_event(db_conn, killer_id, victim_id, event_type):
    exec_query(db_conn, 
    """
    INSERT INTO kills_log (killer_id, victim_id, event_type)
    VALUES (?, ?, ?)
    """, (killer_id, victim_id, event_type))
