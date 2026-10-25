import feedparser
import hashlib
import re
from app.storage.repository import IntentRepository

async def harvest_budget_verified_tasks():
    """
    Scrapes advertised tasks, extracts explicit monetary budgets using regex,
    verifies commercial intent, and structures them for monetization.
    """
    task_feeds = [
        "https://www.upwork.com/ab/feed/jobs/rss?q=paystack%20OR%20stripe%20OR%20fastapi&sort=rec",
        "https://www.upwork.com/ab/feed/jobs/rss?q=database%20bug%20OR%20backend%20urgent&sort=rec"
    ]
    
    harvested_count = 0

    for feed_url in task_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "https://upwork.com")
                
                # Clean up HTML from summary
                clean_summary = re.sub(<.*?>'', summary)
                full_text = f"{title} {clean_summary}"
                
                # --- STEP 1: EXTRACT MONETARY VALUE VIA REGEX ---
                # Looks for patterns like $100, $500.00, USD 200, ₦50,000
                budget_matches = re.findall(r'(\$[\d,]+(?:\.\d{2})?|\bUSD\s*[\d,]+|\bNGN\s*[\d,]+|₦[\d,]+)', full_text)
                
                extracted_budget = 0.0
                if budget_matches:
                    # Clean the first found budget string into a float
                    raw_val = budget_matches[0]
                    num_str = re.sub(r'[^\d.]', '', raw_val)
                    if num_str:
                        extracted_budget = float(num_str)

                # --- STEP 2: VERIFY COMMERCIAL MONETIZATION THRESHOLD ---
                # Only keep tasks that have an explicit advertised budget (e.g., >= $30 or ₦20,000)
                if extracted_budget < 30.0:
                    continue # Skip low-budget or unbudgeted noise

                snippet = clean_summary[:300].replace("\n", " ") + "..."
                task_hash = hashlib.sha256(link.encode()).hexdigest()[:16]
                
                # --- STEP 3: DYNAMIC PRICING FOR MONETIZATION ---
                # Price your automated remediation patch as a fraction of their budget (e.g., 25% of their task budget)
                playbook_price = round(extracted_budget * 0.25, 2)
                if playbook_price < 25.0:
                    playbook_price = 25.0 # Minimum baseline floor

                domain = "Verified High-Budget Commercial Task"
                if "paystack" in full_text.lower() or "stripe" in full_text.lower():
                    domain = "Payment Gateway & Checkout Task"
                elif "database" in full_text.lower() or "sql" in full_text.lower():
                    domain = "Database & Concurrency Task"

                # Save the budget-verified task into SQLite
                await IntentRepository.save_intent(
                    task_hash=task_hash,
                    domain=domain,
                    title=title,
                    snippet=f"[Advertised Budget: ${extracted_budget}] {snippet}",
                    source=link,
                    price=playbook_price
                )
                harvested_count += 1
                print(f"Monetization Lead Captured! Budget: ${extracted_budget} | Playbook Price: ${playbook_price} | {title}")

        except Exception as e:
            print(f"Error parsing budget feeds: {e}")

    print(f"Successfully harvested {harvested_count} budget-verified monetization tasks.")
    return harvested_count
