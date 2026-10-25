from fastapi import APIRouter
from app.storage.database import get_db_path

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "online",
        "mode": "production",
        "database": get_db_path(),
        "engine": "SolveEase IntentForge v3.0"
    }
