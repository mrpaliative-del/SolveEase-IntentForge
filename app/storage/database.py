
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def get_db_connection() -> sqlite3.Connection:
    """Create a configured SQLite connection."""
    database_path = str(settings.DATABASE_PATH)

    # SQLite's special in-memory database needs no filesystem directory.
    if database_path != ":memory:":
        path = Path(database_path).expanduser()
        parent = path.parent

        # Do not attempt to create a persistent-disk mount directory.
        # Render must mount /var/data and grant the process write access.
        if str(parent) == "/var/data" or str(parent).startswith("/var/data/"):
            if not parent.is_dir():
                raise RuntimeError(
                    f"Database directory {parent} does not exist. "
                    "Check that the Render persistent disk is mounted "
                    "at /var/data."
                )
        else:
            parent.mkdir(parents=True, exist_ok=True)

        if not os.access(parent, os.W_OK | os.X_OK):
            raise PermissionError(
                f"Database directory {parent} is not writable by the "
                "application process. Check Render disk permissions "
                "and the Docker runtime user."
            )

    conn = sqlite3.connect(
        database_path,
        timeout=30,
        isolation_level="DEFERRED",
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception:
        conn.close()
        raise

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
