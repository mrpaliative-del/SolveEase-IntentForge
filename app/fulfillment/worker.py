
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.storage.database import db_connection
from app.fulfillment.email import send_fulfillment_email
from app.fulfillment.playbooks import generate_tiered_playbook


logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BASE_RETRY_SECONDS = 15
MAX_RETRY_SECONDS = 3600
STALE_LOCK_SECONDS = 600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def init_fulfillment_queue() -> None:
    """Tables are created by app.storage.database.init_db()."""
    with db_connection() as conn:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fulfillment_task_status
            ON fulfillment_jobs(task_id, status);
        """)


def enqueue_fulfillment(
    task_id: str,
    purchase_reference: str,
    recipient_email: str,
    tier: str,
) -> bool:
    values = [task_id, purchase_reference, recipient_email, tier]

    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("All fulfillment fields must be non-empty strings.")

    now = utc_now()

    with db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO fulfillment_jobs (
                task_id, purchase_reference, recipient_email, tier,
                status, attempts, next_attempt_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, 'pending', 0, %s, %s, %s)
            ON CONFLICT (purchase_reference) DO NOTHING;
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


def _claim_next_job() -> Optional[dict]:
    now = utc_now()
    stale_before = now - timedelta(seconds=STALE_LOCK_SECONDS)

    with db_connection() as conn:
        # Recover jobs abandoned by a crashed process.
        conn.execute("""
            UPDATE fulfillment_jobs
            SET status = CASE
                    WHEN attempts >= %s THEN 'dead'
                    ELSE 'retry'
                END,
                next_attempt_at = %s,
                locked_at = NULL,
                last_error = COALESCE(
                    last_error,
                    'Recovered stale processing job.'
                ),
                updated_at = %s
            WHERE status = 'processing'
              AND locked_at < %s;
        """, (MAX_ATTEMPTS, now, now, stale_before))

        row = conn.execute("""
            SELECT *
            FROM fulfillment_jobs
            WHERE status IN ('pending', 'retry')
              AND next_attempt_at <= %s
              AND attempts < %s
            ORDER BY next_attempt_at, job_id
            FOR UPDATE SKIP LOCKED
            LIMIT 1;
        """, (now, MAX_ATTEMPTS)).fetchone()

        if row is None:
            return None

        cursor = conn.execute("""
            UPDATE fulfillment_jobs
            SET status = 'processing',
                attempts = attempts + 1,
                locked_at = %s,
                updated_at = %s
            WHERE job_id = %s
              AND status IN ('pending', 'retry');
        """, (now, now, row["job_id"]))

        if cursor.rowcount != 1:
            return None

        job = dict(row)
        job["attempts"] = int(row["attempts"]) + 1
        job["status"] = "processing"
        return job


def _schedule_retry(job: dict, error: str) -> None:
    attempts = int(job["attempts"])
    delay = min(
        BASE_RETRY_SECONDS * (2 ** max(0, attempts - 1)),
        MAX_RETRY_SECONDS,
    )
    delay += random.randint(0, min(10, delay // 4 + 1))

    now = utc_now()
    next_attempt = now + timedelta(seconds=delay)
    new_status = "dead" if attempts >= MAX_ATTEMPTS else "retry"

    with db_connection() as conn:
        conn.execute("""
            UPDATE fulfillment_jobs
            SET status = %s,
                next_attempt_at = %s,
                last_error = %s,
                locked_at = NULL,
                updated_at = %s
            WHERE job_id = %s
              AND status = 'processing';
        """, (
            new_status,
            next_attempt,
            error[:500],
            now,
            job["job_id"],
        ))

        conn.execute("""
            UPDATE verified_payments
            SET status = 'failed', updated_at = %s
            WHERE reference = %s
              AND status <> 'sent';
        """, (int(time.time()), job["purchase_reference"]))


def _load_task(task_id: str) -> Optional[dict]:
    with db_connection() as conn:
        row = conn.execute("""
            SELECT task_id, timestamp, source, task_category,
                   raw_signal, micro_price, action
            FROM mega_intent_firehose
            WHERE task_id = %s;
        """, (task_id,)).fetchone()

        return dict(row) if row else None


def _mark_sent(job: dict) -> None:
    now = utc_now()
    epoch = int(time.time())

    with db_connection() as conn:
        conn.execute("""
            UPDATE fulfillment_jobs
            SET status = 'sent',
                last_error = NULL,
                locked_at = NULL,
                updated_at = %s
            WHERE job_id = %s
              AND status = 'processing';
        """, (now, job["job_id"]))

        conn.execute("""
            UPDATE verified_payments
            SET status = 'sent', updated_at = %s
            WHERE reference = %s;
        """, (epoch, job["purchase_reference"]))


def process_next_fulfillment_job() -> bool:
    """Process one due job; return True if a job was claimed."""
    job = _claim_next_job()
    if job is None:
        return False

    try:
        task = _load_task(job["task_id"])

        if task is None:
            _schedule_retry(job, "Task record not found.")
            return True

        raw_signal = task.get("raw_signal")
        if not isinstance(raw_signal, str) or not raw_signal.strip():
            _schedule_retry(job, "Report content is unavailable.")
            return True

        report = generate_tiered_playbook(
            job["tier"],
            raw_signal,
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
            _schedule_retry(
                job,
                "Email provider did not confirm acceptance.",
            )
            return True

        _mark_sent(job)
        logger.info(
            "Fulfillment provider accepted job %s.",
            job["job_id"],
        )
        return True

    except Exception as exc:
        logger.exception(
            "Fulfillment processing failed for job %s.",
            job["job_id"],
        )
        try:
            _schedule_retry(job, str(exc))
        except Exception:
            logger.exception("Unable to schedule fulfillment retry.")
        return True
