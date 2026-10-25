import asyncio
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.health import router as health_router
from app.api.inbound import router as inbound_router
from app.api.payments import router as payments_router
from app.discovery.worker import start_intent_daemon
from app.storage.database import init_db

app = FastAPI(title="SolveEase IntentForge", version="3.0")

app.include_router(health_router)
app.include_router(inbound_router)
app.include_router(payments_router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_landing_page():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "online", "engine": "SolveEase IntentForge v3.0"}

@app.on_event("startup")
async def startup_event():
    # 1. Initialize SQLite Database & Table Schema
    await asyncio.to_thread(init_db)
    
    # 2. Trigger scraper daemon
    asyncio.create_task(start_intent_daemon())
