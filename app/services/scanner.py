import os
import httpx
from app.storage.repository import IntentRepository

async def harvest_live_github_leads():
    """
    Scrapes real-time public developer issues from GitHub 
    targeting active backend and infrastructure pain points.
    """
    # Search queries targeting active production / backend errors
    queries = [
        "FastAPI asyncio error label:bug",
        "Render deployment crash python",
        "Uvicorn worker timeout exception",
        "SQLite database locked WAL mode"
    ]
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "IntentForge-Telemetry-Engine/3.0"
    }
    
    harvested_count = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for q in queries:
            url = f"https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page=3"
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    
                    for item in items:
                        title = item.get("title", "Unknown Issue")
                        body = item.get("body") or "No description provided."
                        # Truncate snippet for storage & review
                        snippet = body[:300].replace("\n", " ") + "..."
                        source_url = item.get("html_url", "https://github.com")
                        
                        # Generate a unique hash for idempotency
                        import hashlib
                        task_hash = hashlib.sha256(source_url.encode()).hexdigest()[:16]
                        
                        # Determine domain based on query keywords
                        domain = "Backend & Concurrency"
                        if "Render" in q or "Docker" in q:
                            domain = "Infrastructure & Deployment"
                        elif "SQLite" in q:
                            domain = "Database Reliability"

                        # Save real lead into SQLite database
                        await IntentRepository.save_intent(
                            task_hash=task_hash,
                            domain=domain,
                            title=title,
                            snippet=snippet,
                            source=source_url,
                            price=15.00  # Standard remediation playbook price in USD/NGN equivalent
                        )
                        harvested_count += 1
                else:
                    print(f"GitHub API returned status {response.status_code} for query: {q}")
            except Exception as e:
                print(f"Error harvesting live leads for '{q}': {e}")

    print(f"Successfully harvested {harvested_count} real live leads from GitHub.")
    return harvested_count
