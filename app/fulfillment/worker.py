
import logging
import random
import sqlite3
import time
from datetime import datetime, timezone
from typing import Optional

from app.storage.database import db_connection
from app.fulfillment.email import send_fulfillment_email
from app.fulfillment.playbooks import generate_tiered_playbook


logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BASE_RETRY_SECONDS = 15
MAX_RETRY_SECONDS = 3600


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_fulfillment_queue() -> None:
    """Create a durable queue for email fulfillment jobs."""
    with db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fulfillment_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                purchase_reference TEXT NOT NULL UNIQUE,
                recipient_email TEXT NOT NULL,
                tier TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN (
                        'pending', 'processing', 'retry',
                        'sent', 'dead'
                    )),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL,
                locked_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fulfillment_due
            ON fulfillment_jobs(status, next_attempt_at);
        """)


def enqueue_fulfillment(
    task_id: str,
    purchase_reference: str,
    recipient_email: str,
    tier: str,
) -> bool:
    """
    Queue a paid purchase after the payment layer has verified it.

    purchase_reference must be the verified, unique payment reference.
    Never call this function based solely on a client checkout redirect.
    """
    values = [
        task_id,
        purchase_reference,
        recipient_email,
        tier,
    ]

    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("All fulfillment fields must be non-empty strings.")

    now = utc_now()

    with db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO fulfillment_jobs (
                task_id, purchase_reference, recipient_email, tier,
                status, attempts, next_attempt_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, ?)
            ON CONFLICT(purchase_reference) DO NOTHING;
        """, (
            task_id.strip(),
            purchase_reference.strip(),
            recipient_email.strip(),
            tier.strip(),
            now,
            now,
            now,
        ))

        return cursor.rowcount == 1


def _claim_job(task_id: str) -> Optional[dict]:
    """
    Atomically claim one due job.

    SQLite's write transaction prevents two workers from claiming the
    same job simultaneously on the same database.
    """
    now = utc_now()

    with db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT *
            FROM fulfillment_jobs
            WHERE task_id = ?
              AND status IN ('pending', 'retry')
              AND next_attempt_at <= ?
              AND attempts < ?
            ORDER BY job_id
            LIMIT 1;
        """, (task_id, now, MAX_ATTEMPTS)).fetchone()

        if row is None:
            return None

        cursor = conn.execute("""
            UPDATE fulfillment_jobs
            SET status = 'processing',
                attempts = attempts + 1,
                locked_at = ?,
                updated_at = ?
            WHERE job_id = ?
              AND status IN ('pending', 'retry');
        """, (now, now, row["job_id"]))

        if cursor.rowcount != 1:
            return None

        claimed = dict(row)
        claimed["attempts"] = row["attempts"] + 1
        return claimed


def _schedule_retry(job: dict, error: str) -> None:
    attempts = job["attempts"]

    delay = min(
        BASE_RETRY_SECONDS * (2 ** max(0, attempts - 1)),
        MAX_RETRY_SECONDS,
    )

    # Jitter prevents synchronized retry bursts.
    delay += random.randint(0, min(10, delay // 4 + 1))

    now = utc_now()
    next_attempt = datetime.fromtimestamp(
        time.time() + delay,
        timezone.utc,
    ).isoformat()

    status = "dead" if attempts >= MAX_ATTEMPTS else "retry"

    with db_connection() as conn:
        conn.execute("""
            UPDATE fulfillment_jobs
            SET status = ?,
                next_attempt_at = ?,
                last_error = ?,
                locked_at = NULL,
                updated_at = ?
            WHERE job_id = ?
              AND status = 'processing';
        """, (
            status,
            next_attempt,
            error[:500],
            now,
            job["job_id"],
        ))


def _mark_sent(job: dict) -> None:
    now = utc_now()

    with db_connection() as conn:
        conn.execute("""
            UPDATE fulfillment_jobs
            SET status = 'sent',
                last_error = NULL,
                locked_at = NULL,
                updated_at = ?
            WHERE job_id = ?
              AND status = 'processing';
        """, (now, job["job_id"]))


def _load_task(task_id: str) -> Optional[dict]:
    with db_connection() as conn:
        row = conn.execute("""
            SELECT task_id, timestamp, source, task_category,
                   raw_signal, micro_price, action
            FROM mega_intent_firehose
            WHERE task_id = ?;
        """, (task_id,)).fetchone()

        return dict(row) if row else None


def process_retryable_job(task_id: str) -> bool:
    """
    Process one due fulfillment job for a task.

    Returns True only when the provider accepts the email and the
    queue records the job as sent. False means no completed delivery
    was recorded; the caller can inspect the queue for its status.
    """
    job = _claim_job(task_id)

    if job is None:
        return False

    try:
        task = _load_task(job["task_id"])

        if task is None:
            _schedule_retry(job, "Task record not found.")
            return False

        # The worker creates the report from the stored signal.
        report = generate_tiered_playbook(
            job["tier"],
            task["raw_signal"],
            source_url=task.get("source"),
            category=task.get("task_category"),
        )

        accepted = send_fulfillment_email(
            to_email=job["recipient_email"],
            task_id=job["task_id"],
            tier=job["tier"],
            solution_content=report,
        )

        if not accepted:
            _schedule_retry(job, "Email provider did not confirm acceptance.")
            return False

        _mark_sent(job)
        return True

    except Exception as exc:
        logger.exception(
            "Fulfillment processing failed for job %s",
            job["job_id"],
        )
        _schedule_retry(job, str(exc))
        return False
