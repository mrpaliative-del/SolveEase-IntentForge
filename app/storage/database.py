import sqlite3
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from app.config import config

executor = ThreadPoolExecutor(max_workers=4)

def get_db_path():
    path = config.DATABASE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

def init_db():
    db_path = get_db_path()
    with sqlite3.connect(db_path, timeout=30.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                task_hash TEXT PRIMARY KEY,
                domain TEXT,
                title TEXT,
                snippet TEXT,
                source TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                reference TEXT PRIMARY KEY,
                email TEXT,
                amount REAL,
                status TEXT,
                playbook_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

async def db_execute(query: str, params: tuple = ()):
    loop = asyncio.get_event_loop()
    db_path = get_db_path()
    
    def _run():
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            return []
            
    return await loop.run_in_executor(executor, _run)
