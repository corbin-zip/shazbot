import shaz_db
import shaz_stats
import re

storm_last_grab_time_remaining = 0 # 60 minutes times 60 seconds = 3600 seconds
storm_last_grab_name = None
inferno_last_grab_time_remaining = 0 # 60 minutes times 60 seconds = 3600 seconds
inferno_last_grab_name = None
current_map = None

def extract_time_remaining(line):
    match = re.search(r'\[(\d+):(\d+)\]', line)
    if match:
        minutes, seconds = map(int, match.groups())
        return minutes * 60 + seconds
    return None

# TODO: consider extracting time from regex instead of passing it around
def handle_cap_event(db_conn, event_type, data, current_time):
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
    
    global storm_last_grab_time_remaining, storm_last_grab_name
    global inferno_last_grab_time_remaining, inferno_last_grab_name
    global current_map

    # print(f"DEBUG: Storm Last Grab Time: {cap_storm_last_grab_time}, Inferno Last Grab Time: {cap_inferno_last_grab_time}")

    higher_grab_time = inferno_last_grab_time_remaining
    if storm_last_grab_time_remaining > inferno_last_grab_time_remaining:
        higher_grab_time = storm_last_grab_time_remaining

    # print(f"DEBUG: Higher Grab Time: {higher_grab_time}")

    #TODO: verify that there is no BUG here -- is it possible to move from eg a 20 minute game to a 60 minute?
    #      i don't think so.
    if current_time > higher_grab_time:
        print(f"DEBUG: Resetting game state (current_time ({current_time}) > higher_grab_time ({higher_grab_time})")
        current_map = None
        storm_last_grab_time_remaining = 3600
        inferno_last_grab_time_remaining = 3600
        storm_last_grab_name = None
        inferno_last_grab_name = None
    
    if event_type == "score_list":
        print(f"DEBUG: Score List Event- current: '{current_map}' new: '{map_name}'")
        return_string = None
        if current_map != map_name:
            return_string = f"Now fastcappin' on {map_name}!"
        current_map = map_name
        return return_string

    if event_type == "took_flag":
        if team_name == "Storm":
            storm_last_grab_name = player_name
            storm_last_grab_time_remaining = current_time
            # print(f"DEBUG: Storm Flag Grabbed: Player = {cap_storm_last_grab_name}, Time = {cap_storm_last_grab_time}")
        if team_name == "Inferno":
            inferno_last_grab_name = player_name
            inferno_last_grab_time_remaining = current_time
            # print(f"DEBUG: Inferno Took Flag: Player = {cap_inferno_last_grab_name}, Time = {cap_inferno_last_grab_time}")
    
    if event_type == "captured_flag":
        if current_map is not None:
            if team_name == "Storm" and storm_last_grab_name == player_name:
                cap_time = storm_last_grab_time_remaining - current_time
                cap_update = record_cap_time(db_conn, storm_last_grab_name, current_map, team_name, cap_time)
                storm_last_grab_time_remaining = 3600
                storm_last_grab_name = None
                return cap_update
            elif team_name == "Inferno" and inferno_last_grab_name == player_name:
                cap_time = inferno_last_grab_time_remaining - current_time
                cap_update = record_cap_time(db_conn, inferno_last_grab_name, current_map, team_name, cap_time)
                inferno_last_grab_time_remaining = 3600
                inferno_last_grab_name = None
                return cap_update
            else:
                return_string = f":( Most recent flag cap for {player_name} on {current_map} ({team_name}) not counted; flag was likely dropped before being capped."
                print(return_string)
                return return_string
        else:
            # TODO: probably replace this with an assert
            return_string = f"!!!!!! BIG PROBLEM: we have a flag cap for {player_name} but we don't know what map we're on!!!!"
            print(return_string)
            return return_string
        
    if event_type == "dropped_flag":
        if team_name == "Storm":
            storm_last_grab_name = None
            storm_last_grab_time_remaining = 3600
        if team_name == "Inferno":
            inferno_last_grab_name = None
            inferno_last_grab_time_remaining = 3600
    return None

def parse_single_cap(db_conn, line, log_file="unmatched_cap_events.log"):
    # TODO: instead of "fixing" the line, i believe we can just fix the regex's to match up to 2 spaces
    fixed_line = re.sub(r"(\[\d{2}:\d{2}\])\s{2}", r"\1 ", line)
    current_time = extract_time_remaining(fixed_line)
    
    if current_time is not None:
        for event, pattern in shaz_stats.EVENT_PATTERNS.items():
            match = re.match(pattern, fixed_line)
            if match:
                cap_update = handle_cap_event(db_conn, event, match.groupdict(), current_time)
                return cap_update
    
    if re.match(r"^\[\d{2}:\d{2}\]", line):
        with open(log_file, "a") as file:
            file.write(f"{line}\n")

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

def record_cap_time(db_conn, player_name, map_name, flag_team, cap_time):
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

    player_id = shaz_db.get_or_create_player(db_conn, player_name)

    assert player_id is not None, f"Error: failed to lookup or create player '{player_name}'"
    
    # query existing time
    current_best = shaz_db.query_stat(db_conn, column, player_id)

    assert current_best is not None, f"Error: no record found for player {player_name} on map {map_name} ({team_name})"

    # compare existing time to new time
    if cap_time < current_best[0]:
        shaz_db.set_stat(db_conn, player_id=player_id, column=column, value=cap_time)
        print(f"Updated {player_name}'s {map_name} ({team_name}) best cap time to {cap_time}.")
        return_string = f":) {player_name} (id {player_id}) set a new personal best on {map_name} ({team_name}) of {cap_time}s!"
    elif cap_time == current_best[0]:
        print(f"{player_name} tied their PB on {map_name} ({team_name}). Current PB is {current_best[0]}s.")
        return_string = f":| {player_name} (id {player_id}) captured the flag on {map_name} ({team_name}) in {cap_time}s, tying their personal best."
    else:
        print(f"{player_name}'s time for {map_name} ({team_name}) was not improved. Current PB is {current_best[0]}s.")
        return_string = f":| {player_name} (id {player_id}) captured the flag on {map_name} ({team_name}) in {cap_time}s, but failed to beat their personal best of {current_best[0]}s."
    
    return return_string
