
import sqlite3
from typing import Optional

from app.storage.database import db_connection


class IntentRepository:
    """Data-access layer for discovered public problem signals."""

    @staticmethod
    def save_task(record: tuple) -> bool:
        """
        Save a task if it does not already exist.

        Expected record order:
        task_hash, task_id, timestamp, source,
        task_category, raw_signal, micro_price, action

        Returns False for duplicate or constraint-invalid records.
        """
        if not isinstance(record, (tuple, list)) or len(record) != 8:
            raise ValueError("record must contain exactly 8 fields")

        try:
            with db_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO mega_intent_firehose (
                        task_hash, task_id, timestamp, source,
                        task_category, raw_signal, micro_price, action
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT DO NOTHING;
                    """,
                    tuple(record),
                )
                return cursor.rowcount == 1

        except sqlite3.IntegrityError:
            # Covers other integrity constraints not handled above.
            return False

    @staticmethod
    def get_latest_tasks(
        limit: int = 10,
        category: Optional[str] = None,
    ) -> list:
        """Return the newest tasks, optionally filtered by category."""
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be an integer")

        limit = max(1, min(limit, 100))

        with db_connection() as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT task_id, timestamp, source, task_category,
                           micro_price, raw_signal, action
                    FROM mega_intent_firehose
                    WHERE task_category = ?
                    ORDER BY timestamp DESC, task_id DESC
                    LIMIT ?;
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT task_id, timestamp, source, task_category,
                           micro_price, raw_signal, action
                    FROM mega_intent_firehose
                    ORDER BY timestamp DESC, task_id DESC
                    LIMIT ?;
                    """,
                    (limit,),
                ).fetchall()

            return [dict(row) for row in rows]

    @staticmethod
    def get_task_by_id(task_id: str) -> Optional[dict]:
        """Return a task record for internal processing, if it exists."""
        if not task_id or not isinstance(task_id, str):
            return None

        with db_connection() as conn:
            row = conn.execute(
                """
                SELECT task_id, timestamp, source, task_category,
                       micro_price, raw_signal, action
                FROM mega_intent_firehose
                WHERE task_id = ?;
                """,
                (task_id,),
            ).fetchone()

            return dict(row) if row else None

    @staticmethod
    def get_total_count() -> int:
        """Return the total number of indexed tasks."""
        with db_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM mega_intent_firehose;"
            ).fetchone()

            return row[0]
