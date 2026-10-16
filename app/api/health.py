
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.storage.database import db_connection
from app.storage.repository import IntentRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """Liveness: confirms the API process can respond."""
    return {
        "status": "healthy",
        "service": "SolveEase IntentForge",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check(response: Response):
    """Readiness: verifies PostgreSQL connectivity and schema."""
    try:
        with db_connection() as conn:
            conn.execute("SELECT 1;")

            row = conn.execute("""
                SELECT to_regclass('public.mega_intent_firehose')
                    AS table_name;
            """).fetchone()

            if not row or row["table_name"] is None:
                raise RuntimeError(
                    "Required discovery table is missing."
                )

        count = IntentRepository.get_total_count()

        return {
            "status": "ready",
            "database": "postgresql",
            "total_stored_tasks": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("IntentForge readiness check failed.")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "Database unavailable or not initialized.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
