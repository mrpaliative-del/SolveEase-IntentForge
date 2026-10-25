import os
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.inbound import router as inbound_router

app = FastAPI(title="IntentForge Commercial Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directory setup
BASE_DIR = Path(__file__).resolve().parent.parent

@app.on_event("startup")
async def startup_db_setup_and_purge():
    try:
        conn = sqlite3.connect("intents.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intents (
                task_hash TEXT PRIMARY KEY,
                domain TEXT,
                title TEXT,
                snippet TEXT,
                source TEXT,
                price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            DELETE FROM intents 
            WHERE source LIKE '%dev.to%' 
               OR source LIKE '%github.com%/pull/%'
               OR source LIKE '%medium.com%'
               OR price < 35;
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Startup DB setup note: {e}")

# Mount API router
app.include_router(inbound_router, prefix="/api/v1")

@app.get("/")
def serve_index():
    # Check absolute path first
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    # Check relative working directory
    if os.path.exists("index.html"):
        return FileResponse("index.html")

    return {
        "status": "online",
        "service": "IntentForge Commercial Lead Engine",
        "endpoints": {
            "live_leads": "/api/v1/inbound/live",
            "docs": "/docs"
        }
    }
