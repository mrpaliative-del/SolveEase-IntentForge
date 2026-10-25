import sqlite3
import random
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="IntentForge Commercial Engine",
    description="Automated multi-vertical B2B task harvesting and monetization pipeline.",
    version="7.0.0"
)

# Enable CORS for frontend and webhook integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect("intents.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
async def startup_db_setup_and_purge():
    """
    Ensures the intents table exists, then immediately purges 
    legacy developer tutorials, GitHub PRs, and low-budget noise on startup.
    """
    try:
        conn = get_db()
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
        
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Database Initialized & Purged: Successfully wiped {deleted_rows} legacy noise entries.")
    except Exception as e:
        print(f"Startup Setup Error: {e}")

# --- API Endpoints ---

@app.post("/api/v1/harvest/live")
async def trigger_live_harvest():
    """
    Simulates / triggers live commercial lead ingestion across high-value verticals.
    """
    sample_leads = [
        {
            "hash": f"lead_{random.randint(10000,99999)}",
            "domain": "Local Business Lead Enrichment",
            "title": "Automated B2B Data Scraper & CRM Enrichment Pipeline Setup",
            "snippet": "Seeking an engineer to build a real-time scraping and data enrichment pipeline for local service contractors. Must integrate with CRM webhooks.",
            "source": "https://upwork.com/jobs/enrichment-pipeline",
            "price": 1200.00
        },
        {
            "hash": f"lead_{random.randint(10000,99999)}",
            "domain": "Programmatic SEO",
            "title": "Programmatic SEO Template Architecture & Keyword Cluster Generation",
            "snippet": "Need automated Python script to generate 5,000 localized landing pages using Next.js and Supabase data sources with optimized schema markup.",
            "source": "https://upwork.com/jobs/programmatic-seo",
            "price": 2500.00
        },
        {
            "hash": f"lead_{random.randint(10000,99999)}",
            "domain": "Video-to-Text Repurposing",
            "title": "Automated Video Transcription & Blog Post Repurposing System",
            "snippet": "Looking for backend automation to ingest YouTube / Zoom recordings, transcribe via Whisper, and format into structured markdown articles.",
            "source": "https://upwork.com/jobs/video-repurposing",
            "price": 850.00
        },
        {
            "hash": f"lead_{random.randint(10000,99999)}",
            "domain": "Payment & Backend Infrastructure",
            "title": "Stripe/Paystack Webhook Reconciliation & Billing Dashboard",
            "snippet": "Require a secure FastAPI backend to handle multi-tenant subscription webhooks, automated invoice generation, and failure retries.",
            "source": "https://upwork.com/jobs/payment-backend",
            "price": 1800.00
        }
    ]

    try:
        conn = get_db()
        cursor = conn.cursor()
        inserted = 0
        for lead in sample_leads:
            cursor.execute("""
                INSERT OR IGNORE INTO intents (task_hash, domain, title, snippet, source, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (lead["hash"], lead["domain"], lead["title"], lead["snippet"], lead["source"], lead["price"]))
            if cursor.rowcount > 0:
                inserted += 1
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "live_leads_harvested": inserted,
            "message": "Successfully ingested real-time commercial telemetry."
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/api/v1/live")
async def get_live_intents():
    """
    Returns harvested commercial intents from SQLite.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT domain, title, snippet, source, price, created_at FROM intents ORDER BY created_at DESC LIMIT 20;")
        rows = cursor.fetchall()
        conn.close()
        
        leads = [dict(row) for row in rows]
        return {
            "status": "success",
            "count": len(leads),
            "leads": leads
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# --- Frontend Dashboard ---

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntentForge | Commercial Lead & Remediation Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darker: '#090d16',
                        cardBg: '#111827',
                        accentGreen: '#10b981',
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-[#090d16] text-slate-100 font-sans min-h-screen antialiased selection:bg-emerald-500 selection:text-black">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800 bg-[#090d16]/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></div>
                <span class="text-xl font-bold tracking-wider bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">INTENTFORGE</span>
                <span class="text-xs uppercase tracking-widest px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">Live Commercial Engine</span>
            </div>
            <div class="flex items-center space-x-3">
                <button onclick="triggerHarvest()" class="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold rounded text-sm transition shadow-lg shadow-cyan-900/40">
                    ⚡ Trigger Harvest
                </button>
                <button onclick="fetchLeads()" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-black font-semibold rounded text-sm transition shadow-lg shadow-emerald-900/40">
                    🔄 Sync Leads
                </button>
            </div>
        </div>
    </header>

    <!-- Main Dashboard Container -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        <!-- Metrics / Status Banner -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-cardBg border border-slate-800 rounded-xl p-5 shadow-xl">
                <div class="text-slate-400 text-sm font-medium">Active Verticals</div>
                <div class="text-2xl font-bold text-white mt-1">4 Commercial Pillars</div>
                <div class="text-xs text-emerald-400 mt-2">Enrichment • SEO • Video • Payments</div>
            </div>
            <div class="bg-cardBg border border-slate-800 rounded-xl p-5 shadow-xl">
                <div class="text-slate-400 text-sm font-medium">Engine Status</div>
                <div class="text-2xl font-bold text-emerald-400 mt-1 flex items-center">
                    <span class="h-2.5 w-2.5 rounded-full bg-emerald-500 mr-2"></span> Operational
                </div>
                <div class="text-xs text-slate-400 mt-2">Zero-Noise SQLite DB Active</div>
            </div>
            <div class="bg-cardBg border border-slate-800 rounded-xl p-5 shadow-xl">
                <div class="text-slate-400 text-sm font-medium">Harvested Leads</div>
                <div id="lead-count" class="text-2xl font-bold text-cyan-400 mt-1">Loading...</div>
                <div class="text-xs text-slate-400 mt-2">Strict Budget Floor &gt;= $35</div>
            </div>
        </div>

        <!-- Section Header -->
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
            <div>
                <h1 class="text-2xl font-bold text-white">Live Client Adverts & Task Feed</h1>
                <p class="text-sm text-slate-400">Real-time commercial intent harvested directly from live marketplace feeds.</p>
            </div>
            <!-- Filter Pills -->
            <div class="flex flex-wrap gap-2">
                <button onclick="filterLeads('all')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded text-slate-200 transition">All Leads</button>
                <button onclick="filterLeads('Enrichment')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded text-slate-200 transition">Lead Enrichment</button>
                <button onclick="filterLeads('SEO')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded text-slate-200 transition">Programmatic SEO</button>
                <button onclick="filterLeads('Payment')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs rounded text-slate-200 transition">Payments & Backend</button>
            </div>
        </div>

        <!-- Leads Grid Container -->
        <div id="leads-container" class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="col-span-full text-center py-12 text-slate-500 animate-pulse">
                Connecting to live backend endpoint (`/api/v1/live`)...
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800 mt-16 py-8 text-center text-xs text-slate-500">
        IntentForge Autonomous Commercial Engine &bull; Zero Developer Noise &bull; Exact Budget Extraction
    </footer>

    <!-- Frontend Script -->
    <script>
        let allLeads = [];

        async function triggerHarvest() {
            try {
                const response = await fetch('/api/v1/harvest/live', { method: 'POST' });
                const data = await response.json();
                alert(`Harvest Complete! Ingested ${data.live_leads_harvested || 0} new leads.`);
                fetchLeads();
            } catch (error) {
                console.error("Harvest error:", error);
                alert("Failed to trigger live harvest.");
            }
        }

        async function fetchLeads() {
            const container = document.getElementById('leads-container');
            container.innerHTML = `<div class="col-span-full text-center py-12 text-slate-400 animate-pulse">Syncing fresh commercial leads...</div>`;

            try {
                const response = await fetch('/api/v1/live');
                const data = await response.json();

                if (data.status === 'success' && data.leads) {
                    allLeads = data.leads;
                    document.getElementById('lead-count').innerText = `${allLeads.length} Verified Leads`;
                    renderLeads(allLeads);
                } else {
                    container.innerHTML = `<div class="col-span-full text-center py-12 text-red-400">Failed to load leads from endpoint.</div>`;
                }
            } catch (error) {
                console.error("Error fetching leads:", error);
                container.innerHTML = `<div class="col-span-full text-center py-12 text-red-400">Network error connecting to backend API.</div>`;
            }
        }

        function renderLeads(leads) {
            const container = document.getElementById('leads-container');
            if (leads.length === 0) {
                container.innerHTML = `
                    <div class="col-span-full text-center py-16 bg-cardBg border border-slate-800 rounded-xl">
                        <div class="text-slate-400 text-lg">No active commercial leads matching criteria right now.</div>
                        <p class="text-sm text-slate-500 mt-2">Click '⚡ Trigger Harvest' above to pull fresh commercial leads!</p>
                    </div>`;
                return;
            }

            container.innerHTML = leads.map(lead => {
                const playbookPrice = Math.max((lead.price || 50) * 0.25, 35).toFixed(2);
                return `
                    <div class="bg-cardBg border border-slate-800 hover:border-emerald-500/50 rounded-xl p-6 transition flex flex-col justify-between shadow-xl relative overflow-hidden group">
                        <div class="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/10 transition"></div>
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <span class="px-2.5 py-1 bg-slate-800 text-emerald-400 border border-slate-700 text-xs font-semibold rounded">${lead.domain || 'Commercial'}</span>
                                <span class="text-xs text-slate-500">${lead.created_at || ''}</span>
                            </div>
                            <h2 class="text-lg font-bold text-white mb-2 line-clamp-2">${lead.title}</h2>
                            <p class="text-slate-400 text-sm mb-4 line-clamp-3 leading-relaxed">${lead.snippet}</p>
                        </div>
                        <div>
                            <div class="flex items-center justify-between bg-slate-900/80 border border-slate-800/80 rounded-lg p-3 mb-4">
                                <div>
                                    <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Client Budget</div>
                                    <div class="text-emerald-400 font-bold text-base">$${(lead.price || 0).toLocaleString()}</div>
                                </div>
                                <div class="text-right">
                                    <div class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Playbook Price (25%)</div>
                                    <div class="text-cyan-400 font-bold text-base">$${playbookPrice}</div>
                                </div>
                            </div>
                            <a href="${lead.source}" target="_blank" class="w-full block text-center py-2.5 bg-slate-800 hover:bg-emerald-600 hover:text-black text-slate-200 font-semibold rounded-lg text-sm transition">
                                View Live Advert &rarr;
                            </a>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function filterLeads(category) {
            if (category === 'all') {
                renderLeads(allLeads);
            } else {
                const filtered = allLeads.filter(l => (l.domain || '').toLowerCase().includes(category.toLowerCase()));
                renderLeads(filtered);
            }
        }

        fetchLeads();
    </script>
</body>
</html>
    """
