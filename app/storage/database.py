import sqlite3
import os
from app.config import config

def get_db_path():
    db_dir = os.path.dirname(config.DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return config.DATABASE_PATH

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode for high concurrency
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # Create the intents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_hash TEXT UNIQUE NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            snippet TEXT NOT NULL,
            source TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def db_execute(query: str, params: tuple = ()):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    if query.strip().upper().startswith("SELECT"):
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    else:
        conn.commit()
        conn.close()
        return cursor.rowcount
