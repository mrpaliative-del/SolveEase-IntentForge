import asyncio
import httpx
from fastapi import FastAPI
from app.storage.database import init_db
from app.api.health import router as health_router
from app.api.inbound import router as inbound_router
from app.api.payments import router as payments_router
from app.discovery.worker import start_intent_daemon

app = FastAPI(
    title="SolveEase IntentForge Live Monetization Engine v3.0",
    version="3.0.0"
)

app.include_router(health_router)
app.include_router(inbound_router)
app.include_router(payments_router)

@app.on_event("startup")
async def on_startup():
    init_db()
    asyncio.create_task(start_intent_daemon())
    
    async def keep_alive():
        while True:
            await asyncio.sleep(600)
            try:
                async with httpx.AsyncClient() as client:
                    await client.get("https://market-alert-dzas.onrender.com/health")
            except Exception:
                pass

    asyncio.create_task(keep_alive())
