import httpx
import hashlib
import re
import feedparser
from app.storage.repository import IntentRepository

async def harvest_multivertical_leads():
    """
    Scrapes live commercial task marketplaces in real-time across your 4 business directions,
    extracting exact high-value client budgets, verbatim task narrations, and filtering out noise.
    """
    
    # Real-time search endpoints targeting high-intent commercial tasks
    live_endpoints = [
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=clay%20OR%20gohighlevel%20OR%20crm%20automation&sort=rec",
            "vertical": "Local Business Lead Enrichment"
        },
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=programmatic%20seo%20OR%20shopify%20automation%20OR%20wordpress%20scaling&sort=rec",
            "vertical": "Programmatic SEO & Content"
        },
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=podcast%20repurposing%20OR%20youtube%20transcript%20pipeline&sort=rec",
            "vertical": "Video-to-Text & Social Snippets"
        },
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=paystack%20integration%20OR%20stripe%20webhook%20error&sort=rec",
            "vertical": "Payment & Backend Infrastructure"
        }
    ]
    
    # Negative filters to eliminate tutorials, blogs, and code repositories
    noise_filters = [
        "tutorial", "how to", "guide", "walkthrough", "github.com", "dev.to", 
        "medium.com", "substack", "clone", "boilerplate", "template", "open source"
    ]
    
    harvested_count = 0
    headers = {"User-Agent": "IntentForge-Live-Engine/5.0"}

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for ep in live_endpoints:
            feed_url = ep["url"]
            vertical_name = ep["vertical"]

            try:
                response = await client.get(feed_url)
                if response.status_code != 200:
                    continue

                feed = feedparser.parse(response.text)
                for entry in feed.entries[:6]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "").strip()
                    link = entry.get("link", "").strip()
                    
                    if not link:
                        continue

                    # Clean HTML tags to get the verbatim task narration written by the client
                    verbatim_narration = re.sub(r'<.*?>', '', summary).strip()
                    full_text = f"{title} {verbatim_narration}".lower()
                    
                    # Drop any developer tutorials or noise
                    if any(noise in full_text or noise in link.lower() for noise in noise_filters):
                        continue

                    # --- EXACT BUDGET EXTRACTION VIA REGEX ---
                    # Captures real advertised figures (e.g., $250, $1,500, USD 500, ₦200,000)
                    budget_matches = re.findall(r'(\$[\d,]+(?:\.\d{2})?|\bUSD\s*[\d,]+|\bNGN\s*[\d,]+|₦[\d,]+)', full_text)
                    
                    exact_budget = 0.0
                    if budget_matches:
                        raw_val = budget_matches[0]
                        num_str = re.sub(r'[^\d.]', '', raw_val)
                        if num_str:
                            exact_budget = float(num_str)

                    # High-Value Monetization Floor: Only keep real gigs with budgets >= $50
                    if exact_budget < 50.0:
                        continue

                    task_hash = hashlib.sha256(link.encode()).hexdigest()[:16]
                    
                    # Automated Solution Pricing (25% of the client's advertised budget)
                    playbook_price = round(exact_budget * 0.25, 2)
                    if playbook_price < 35.0:
                        playbook_price = 35.0

                    # Save real live lead with verbatim narration and exact budget into SQLite
                    await IntentRepository.save_intent(
                        task_hash=task_hash,
                        domain=vertical_name,
                        title=title,
                        snippet=verbatim_narration[:500] + "...",
                        source=link,
                        price=exact_budget
                    )
                    harvested_count += 1
                    print(f"[LIVE MONETIZATION LEAD] [{vertical_name}] Budget: ${exact_budget} | Title: {title}")

            except Exception as e:
                print(f"Error fetching live marketplace feed {feed_url}: {e}")

    print(f"Successfully synchronized {harvested_count} real-time high-value commercial leads.")
    return harvested_count

# Aliases for router compatibility
harvest_live_github_leads = harvest_multivertical_leads
harvest_monetization_leads = harvest_multivertical_leads
harvest_advertised_tasks = harvest_multivertical_leads
