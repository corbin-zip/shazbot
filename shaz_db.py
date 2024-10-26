#!/usr/bin/python

import sqlite3

# Create or connect to the SQLite database and set up the schema
def initialize_database(player_table_init: str, kills_log_table_init: str, db_name="game_log.db"):
    db_conn = sqlite3.connect(db_name, check_same_thread=False)
    cursor = db_conn.cursor()

    # TODO: this *likely* doesn't include everything we want to track;
    #       need to verify that.
    cursor.execute(player_table_init)
    cursor.execute(kills_log_table_init)

    db_conn.commit()
    return db_conn

# Get player ID by name, create player if they don't exist
def get_or_create_player(db_conn, player_name):
    cursor = db_conn.cursor()
    cursor.execute("SELECT id FROM players WHERE name = ?", (player_name,))
    row = cursor.fetchone()

    if row:
        return row[0]
    else:
        cursor.execute("INSERT INTO players (name) VALUES (?)", (player_name,))
        db_conn.commit()
        return cursor.lastrowid


def query_stat(db_conn, column: str, player_id):
    cursor = db_conn.cursor()
    # query existing time
    cursor.execute(f"SELECT {column} FROM players WHERE id = ?", (player_id,))
    return cursor.fetchone()

def exec_query(db_conn, query: str, params: tuple = ()):
    cursor = db_conn.cursor()
    cursor.execute(query, params)
    db_conn.commit()

# TODO: use query_stat() instead
def get_player_name_by_id(db_conn, player_id):
    cursor = db_conn.cursor()
    cursor.execute("SELECT name FROM players WHERE id = ?", (player_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def set_stat(db_conn, player_id, column, value):
    exec_query(f"UPDATE players SET {column} = ? WHERE id = ?", (value, player_id))

# BUG TODO: merge function is broken for fastcap and will trample the player's scores
def merge_players(db_conn, source_id, target_id):
    cursor = db_conn.cursor()

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

    db_conn.commit()

def whois(db_conn, player_name):
    cursor = db_conn.cursor()
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

def close_db(db_conn):
    db_conn.close()

############# testing. comment this out when using shazbot.py instead ##################
# conn = initialize_database()

# if len(sys.argv) > 1:
#     argument = sys.argv[1]
#     with open(argument, "r") as log_file:
#         for line in log_file:
#             parse_single_stat(conn, line)
            
# conn.close()
