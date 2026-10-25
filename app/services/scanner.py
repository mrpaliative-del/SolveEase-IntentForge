import feedparser
import hashlib
import re
from app.storage.repository import IntentRepository

async def harvest_multivertical_leads():
    """
    Scrapes high-intent monetizable leads across 4 key verticals:
    1. Technical & Payment Infrastructure Emergencies (GitHub/Gigs)
    2. Local Business Lead Enrichment & CRM Automation Tasks
    3. Programmatic SEO & E-Commerce Blog Generation Requests
    4. Video-to-Text Transcription & Social Snippet Tasks
    """
    
    # Define categorized RSS feeds and search targets
    vertical_feeds = [
        # Vertical 1: Payment & Backend Infrastructure
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=paystack%20OR%20stripe%20OR%20fastapi&sort=rec",
            "vertical": "Payment & Backend Infrastructure",
            "default_price": 75.0
        },
        # Vertical 2: Local Business Lead Enrichment & CRM Sync
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=lead%20enrichment%20OR%20clay%20OR%20gohighlevel&sort=rec",
            "vertical": "Local Business Lead Enrichment",
            "default_price": 50.0
        },
        # Vertical 3: Programmatic SEO & E-Commerce Content
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=shopify%20blog%20OR%20programmatic%20seo%20OR%20wordpress%20automation&sort=rec",
            "vertical": "Programmatic SEO & Content",
            "default_price": 40.0
        },
        # Vertical 4: Video Transcription & Social Repurposing
        {
            "url": "https://www.upwork.com/ab/feed/jobs/rss?q=youtube%20transcript%20OR%20podcast%20repurposing%20OR%20whisper&sort=rec",
            "vertical": "Video-to-Text & Social Snippets",
            "default_price": 45.0
        }
    ]
    
    harvested_count = 0

    for feed_info in vertical_feeds:
        feed_url = feed_info["url"]
        vertical_name = feed_info["vertical"]
        base_price = feed_info["default_price"]

        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]: # Top 3 fresh posts per vertical
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "https://upwork.com")
                
                # Clean up HTML tags
                clean_summary = re.sub(r'<.*?>', '', summary)
                full_text = f"{title} {clean_summary}"
                
                # --- STEP 1: EXTRACT EXPLICIT BUDGET VIA REGEX ---
                budget_matches = re.findall(r'(\$[\d,]+(?:\.\d{2})?|\bUSD\s*[\d,]+|\bNGN\s*[\d,]+|₦[\d,]+)', full_text)
                
                extracted_budget = base_price
                if budget_matches:
                    raw_val = budget_matches[0]
                    num_str = re.sub(r'[^\d.]', '', raw_val)
                    if num_str and float(num_str) > 10.0:
                        extracted_budget = float(num_str)

                snippet = clean_summary[:300].replace("\n", " ") + "..."
                task_hash = hashlib.sha256(link.encode()).hexdigest()[:16]
                
                # --- STEP 2: DYNAMIC PLAYBOOK PRICING ---
                # Price the automated remediation/workflow solution as a fraction of their budget
                playbook_price = round(extracted_budget * 0.25, 2)
                if playbook_price < 25.0:
                    playbook_price = 25.0 # Baseline floor

                # Save the enriched multi-vertical lead into SQLite database
                await IntentRepository.save_intent(
                    task_hash=task_hash,
                    domain=vertical_name,
                    title=title,
                    snippet=f"[Advertised Budget: ~${extracted_budget}] {snippet}",
                    source=link,
                    price=playbook_price
                )
                harvested_count += 1
                print(f"[{vertical_name}] Lead Captured! Budget: ${extracted_budget} | Solution Price: ${playbook_price} | {title}")

        except Exception as e:
            print(f"Error polling feed {feed_url}: {e}")

    print(f"Successfully polled and synchronized {harvested_count} multi-vertical monetization leads.")
    return harvested_count

# Aliases for compatibility across your API routers
harvest_live_github_leads = harvest_multivertical_leads
harvest_monetization_leads = harvest_multivertical_leads
harvest_advertised_tasks = harvest_multivertical_leads
