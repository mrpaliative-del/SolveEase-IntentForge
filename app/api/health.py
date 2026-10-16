
import logging
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.config import settings
from app.storage.repository import IntentRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Liveness check: confirms the API process can respond.
    Does not require the database to be available.
    """
    return {
        "status": "healthy",
        "service": "SolveEase IntentForge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(response: Response):
    """
    Readiness check: confirms the configured SQLite database is usable.
    Returns HTTP 503 if the database is not ready.
    """
    database_path = settings.DATABASE_PATH

    try:
        # Verify actual database connectivity rather than relying only
        # on os.path.exists(), which can be misleading for SQLite.
        with sqlite3.connect(database_path, timeout=3) as conn:
            conn.execute("PRAGMA busy_timeout = 3000;")
            conn.execute("SELECT 1;")

            # Check that the expected table exists.
            table = conn.execute("""
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'mega_intent_firehose'
                LIMIT 1;
            """).fetchone()

            if table is None:
                raise RuntimeError("Required database table is missing.")

        count = IntentRepository.get_total_count()

        return {
            "status": "ready",
            "total_stored_tasks": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except (sqlite3.Error, OSError, RuntimeError):
        logger.exception("IntentForge readiness check failed.")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "not_ready",
            "reason": "Database unavailable or not initialized.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("Unexpected readiness check failure.")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "not_ready",
            "reason": "Readiness check failed.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
