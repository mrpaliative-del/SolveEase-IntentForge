import sqlite3
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.inbound import router as inbound_router

app = FastAPI(
    title="IntentForge Commercial Engine",
    description="Automated multi-vertical B2B task harvesting and monetization pipeline.",
    version="6.3.0"
)

# Enable CORS for frontend and webhook integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_setup_and_purge():
    """
    Ensures the intents table exists, then immediately purges 
    legacy developer tutorials, GitHub PRs, and low-budget noise on startup.
    """
    try:
        conn = sqlite3.connect("intents.db")
        cursor = conn.cursor()
        
        # Ensure table exists
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
        
        # Wipe legacy noise
        cursor.execute("""
            DELETE FROM intents 
            WHERE source LIKE '%dev.to%' 
               OR source LIKE '%github.com%/pull/%'
               OR source LIKE '%medium.com%'
               OR price < 35;
        """)
        
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Database Initialized & Purged: Successfully wiped {deleted_rows} legacy noise entries.")
    except Exception as e:
        print(f"Startup Setup Error: {e}")

# Include API routers under /api/v1
app.include_router(inbound_router, prefix="/api/v1")

@app.get("/")
def serve_frontend():
    """
    Robustly serves index.html from any standard directory location.
    """
    possible_paths = [
        "index.html",
        "public/index.html",
        "static/index.html",
        "../index.html"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
            
    # Fallback status if index.html is truly missing
    return {
        "status": "online",
        "service": "IntentForge Commercial Lead Engine",
        "endpoints": {
            "live_leads": "/api/v1/inbound/live",
            "docs": "/docs"
        }
    }
