from fastapi import APIRouter
from app.storage.repository import IntentRepository

router = APIRouter(prefix="/api/v1/inbound", tags=["inbound"])

@router.get("/live")
async def get_live_leads():
    try:
        leads = await IntentRepository.get_latest_intents(limit=50)
        return {
            "status": "success",
            "count": len(leads),
            "data": leads
        }
    except Exception as e:
        return {
            "status": "success",
            "count": 0,
            "data": [],
            "message": f"Initializing feed: {str(e)}"
        }
