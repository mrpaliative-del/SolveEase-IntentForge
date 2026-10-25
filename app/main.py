import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.inbound import router as inbound_router

app = FastAPI(
    title="IntentForge Commercial Engine",
    description="Automated multi-vertical B2B task harvesting and monetization pipeline.",
    version="6.0.0"
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
async def startup_db_cleanup():
    """
    Automatically purges legacy dev articles, GitHub pull requests, 
    and low-budget noise from the SQLite database on startup.
    """
    try:
        # Connect to your SQLite database (adjust filename if your repo uses another path)
        conn = sqlite3.connect("intents.db")
        cursor = conn.cursor()
        
        # Delete legacy mock/tutorial/GitHub PR noise and low-value items
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
        print(f"Startup Purge: Successfully wiped {deleted_rows} legacy noise entries from database.")
    except Exception as e:
        print(f"Startup Purge Note (Table might not exist yet): {e}")

# Include your inbound API and scanner routers
app.include_router(inbound_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "IntentForge Commercial Lead Engine",
        "endpoints": {
            "live_leads": "/api/v1/inbound/live",
            "docs": "/docs"
        }
    }
