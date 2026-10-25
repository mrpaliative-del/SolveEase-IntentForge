from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio

from app.api.health import router as health_router
from app.api.inbound import router as inbound_router
from app.api.payments import router as payments_router
from app.discovery.worker import start_intent_daemon

app = FastAPI(title="SolveEase IntentForge", version="3.0")

# Mount API Routers
app.include_router(health_router)
app.include_router(inbound_router)
app.include_router(payments_router)

# Setup static directory for the landing page frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount static files if the directory exists
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_landing_page():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "status": "online",
        "engine": "SolveEase IntentForge v3.0",
        "endpoints": {
            "health": "/health",
            "live_leads": "/api/v1/inbound/live",
            "webhook": "/api/v1/payment/webhook"
        }
    }

@app.on_event("startup")
async def startup_event():
    # Start the autonomous multi-vector harvesting background daemon on boot
    asyncio.create_task(start_intent_daemon())
