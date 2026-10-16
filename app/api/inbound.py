
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.storage.repository import IntentRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/v1/inbound/live")
async def get_live_inbound_intent(
    limit: int = Query(default=10, ge=1, le=100),
    category: Optional[str] = Query(default=None, min_length=1, max_length=100),
):
    """
    Return recent, publishable problem-intent candidates.

    Only records explicitly marked 'published' should be exposed publicly.
    Raw source content must be sanitized before publication.
    """
    try:
        rows = IntentRepository.get_latest_tasks(
            limit=limit,
            category=category.strip() if category else None,
        )

        live_tasks = []

        for row in rows:
            # Supports dictionary rows returned by the refined repository.
            task = dict(row)

            # Public API allowlist: do not expose raw_signal or internal fields.
            live_tasks.append({
                "task_id": task.get("task_id"),
                "timestamp": task.get("timestamp"),
                "source": task.get("source"),
                "category": task.get("task_category"),
                "bounty_price": task.get("micro_price"),
                "status": task.get("action"),
            })

        return {
            "status": "success",
            "returned_count": len(live_tasks),
            "limit": limit,
            "category": category.strip() if category else None,
            "inbound_tasks": live_tasks,
        }

    except Exception:
        logger.exception("Failed to retrieve live inbound intent.")
        raise HTTPException(
            status_code=503,
            detail="The live intent feed is temporarily unavailable.",
        )
