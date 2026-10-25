import os
import httpx
import hashlib
from app.storage.repository import IntentRepository

async def harvest_monetization_leads():
    """
    Scrapes high-intent commercial and financial infrastructure pain points 
    where businesses experience revenue leakage or system downtime.
    """
    # High-intent commercial and transactional queries
    commercial_queries = [
        "Paystack webhook verification failed python",
        "Stripe checkout session error production",
        "FastAPI payment processing race condition",
        "database deadlock financial transaction error"
    ]
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "IntentForge-Monetization-Engine/3.0"
    }
    
    harvested_count = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for q in commercial_queries:
            url = f"https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page=2"
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    
                    for item in items:
                        title = item.get("title", "Unknown Transaction Issue")
                        body = item.get(vector for vector in [item.get("body")]) or "Commercial transaction pipeline friction detected."
                        snippet = body[:300].replace("\n", " ") + "..."
                        source_url = item.get("html_url", "https://github.com")
                        
                        task_hash = hashlib.sha256(source_url.encode()).hexdigest()[:16]
                        
                        # Classify into high-value monetization categories
                        domain = "Payment & Transaction Integrity"
                        if "database" in q or "deadlock" in q:
                            domain = "Ledger & Database Concurrency"

                        # Log as a high-value commercial lead ($45 - $150 remediation value)
                        await IntentRepository.save_intent(
                            task_hash=task_hash,
                            domain=domain,
                            title=title,
                            snippet=snippet,
                            source=source_url,
                            price=45.00  
                        )
                        harvested_count += 1
                else:
                    print(f"Commercial search API status {response.status_code} for query: {q}")
            except Exception as e:
                print(f"Error harvesting commercial leads: {e}")

    print(f"Successfully harvested {harvested_count} high-intent monetization leads.")
    return harvested_count
