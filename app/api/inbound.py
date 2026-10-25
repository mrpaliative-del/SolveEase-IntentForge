from fastapi import APIRouter
from app.services.scanner import harvest_live_github_leads
from app.storage.repository import IntentRepository

# Remove the redundant prefix here since main.py already prefixes with /api/v1
router = APIRouter(tags=["inbound"])

@router.post("/harvest/live")
async def trigger_live_harvest():
    count = await harvest_live_github_leads()
    return {
        "status": "success",
        "live_leads_harvested": count,
        "message": "Successfully ingested real-time commercial telemetry."
    }

@router.get("/live")
async def get_live_intents():
    intents = await IntentRepository.get_latest_intents(limit=20)
    return {
        "status": "success",
        "count": len(intents),
        "leads": intents
    }
