import asyncio
from datetime import datetime
import shaz_db
import shaz_stats

session_list = []

def create_session(name: str, channel: str):
    # TODO: verify the channel here or when called
    
    date = datetime.now().strftime('%m-%d-%y')
    filename = f"{date} {name}.db"

    db_conn = shaz_db.initialize_database(
        player_table_init=shaz_stats.PLAYER_TABLE_INIT,
        kills_log_table_init=shaz_stats.KILLS_LOG_TABLE_INIT,
        db_name=filename
    )

    session_lock = asyncio.Lock()

    session = {
        "name": name,
        "date": date,
        "channel": channel,
        "filename": filename,
        "db_conn": db_conn,
        "lock": session_lock
    }
    session_list.append(session)

def list_sessions() -> str:
    if not session_list:
        return "No sessions found."
    return "\n".join(
        [f"{i+1}. {session['name']} - {session['date']} (Channel: {session['channel']})" 
         for i, session in enumerate(session_list)]
    )

def is_channel_in_session_list(channel: str) -> tuple[bool, object | None, asyncio.Lock | None]:
    normalized_channel = f"#{channel.lstrip('#')}"

    for session in session_list:
        if session["channel"] == normalized_channel:
            return True, session["db_conn"], session["lock"]
    return False, None, None

# end session by channel name, close db, & remove from list
def end_session(channel: str) -> bool:
    global session_list
    for i, session in enumerate(session_list):
        if session["channel"] == channel:
            shaz_db.close_db(session["db_conn"])
            del session_list[i]
            print(f"Session for channel {channel} ended.")
            return True
    print(f"No session found for channel {channel}.")
    return False