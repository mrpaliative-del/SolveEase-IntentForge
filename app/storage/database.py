
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def get_db_connection() -> sqlite3.Connection:
    """Create a configured SQLite connection."""
    database_path = settings.DATABASE_PATH

    # Allow SQLite's special in-memory database.
    if database_path != ":memory:":
        Path(database_path).expanduser().parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    conn = sqlite3.connect(
        database_path,
        timeout=30,
        isolation_level="DEFERRED",
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    return conn


@contextmanager
def db_connection():
    """Commit successful operations and roll back failures."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema and indexes."""
    with db_connection() as conn:
        # WAL mode is persistent for a file-backed database.
        if settings.DATABASE_PATH != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS mega_intent_firehose (
                task_hash TEXT PRIMARY KEY,
                task_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                task_category TEXT NOT NULL,
                raw_signal TEXT NOT NULL,
                micro_price INTEGER NOT NULL
                CHECK (micro_price BETWEEN 100 AND 500),
                action TEXT NOT NULL DEFAULT 'pending'
                CHECK (
                    action IN (
                        'pending',
                        'published',
                        'sold',
                        'archived'
                    )
                )
            );
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mega_price
            ON mega_intent_firehose(micro_price);
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mega_timestamp
            ON mega_intent_firehose(timestamp);
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mega_category_action
            ON mega_intent_firehose(task_category, action);
        """)
