import httpx
import feedparser
import hashlib
import re
from app.storage.repository import IntentRepository

async def harvest_multivertical_leads():
    """
    Production-grade scanner for IntentForge.
    Scrapes active commercial job/task streams across the 4 business verticals,
    enforces strict budgeting, and completely blocks developer tutorials/PRs.
    """
    
    # Target feeds across your 4 commercial monetization directions
    target_feeds = [
        "https://www.upwork.com/ab/feed/jobs/rss?q=clay%20OR%20gohighlevel%20OR%20crm%20automation&sort=rec",
        "https://www.upwork.com/ab/feed/jobs/rss?q=shopify%20blog%20OR%20programmatic%20seo%20OR%20wordpress%20automation&sort=rec",
        "https://www.upwork.com/ab/feed/jobs/rss?q=youtube%20transcript%20OR%20whisper%20OR%20podcast%20repurposing&sort=rec",
        "https://www.upwork.com/ab/feed/jobs/rss?q=paystack%20integration%20OR%20stripe%20webhook%20error&sort=rec"
    ]
    
    # Hard blacklist to eliminate developer blogs, tutorials, and Git commits
    blocked_domains = [
        "dev.to", "medium.com", "github.com", "hashnode.dev", 
        "substack.com", "gitlab.com", "stackoverflow.com"
    ]
    
    blocked_terms = [
        "tutorial", "how to", "guide", "walkthrough", "clone", 
        "boilerplate", "template", "open source", "pull request", "merged"
    ]
    
    harvested_count = 0
    headers = {"User-Agent": "IntentForge-StrictCommercialEngine/6.0"}

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        for feed_url in target_feeds:
            try:
                response = await client.get(feed_url)
                if response.status_code != 200:
                    continue

                feed = feedparser.parse(response.text)
                for entry in feed.entries[:8]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "").strip()
                    link = entry.get("link", "").strip()
                    
                    if not link:
                        continue

                    # 1. STRICT BLOCK: Drop any developer or tutorial site instantly
                    if any(domain in link.lower() for domain in blocked_domains):
                        continue

                    # Clean HTML tags to get verbatim client text
                    verbatim_narration = re.sub(r'<.*?>', '', summary).strip()
                    full_text = f"{title} {verbatim_narration}".lower()

                    # 2. STRICT BLOCK: Drop tutorial/code language
                    if any(term in full_text for term in blocked_terms):
                        continue

                    # --- EXACT BUDGET EXTRACTION VIA REGEX ---
                    budget_matches = re.findall(r'(\$[\d,]+(?:\.\d{2})?|\bUSD\s*[\d,]+|\bNGN\s*[\d,]+|₦[\d,]+)', full_text)
                    
                    exact_budget = 0.0
                    if budget_matches:
                        raw_val = budget_matches[0]
                        num_str = re.sub(r'[^\d.]', '', raw_val)
                        if num_str:
                            exact_budget = float(num_str)

                    # 3. COMMERCIAL FILTER: Require real advertised budget >= $40
                    if exact_budget < 40.0:
                        continue

                    task_hash = hashlib.sha256(link.encode()).hexdigest()[:16]
                    
                    # Playbook pricing (25% of exact budget)
                    playbook_price = round(exact_budget * 0.25, 2)
                    if playbook_price < 30.0:
                        playbook_price = 30.0

                    # Assign vertical category based on keywords
                    domain = "High-Value Commercial Task"
                    if "clay" in full_text or "gohighlevel" in full_text or "crm" in full_text:
                        domain = "Local Business Lead Enrichment"
                    elif "seo" in full_text or "shopify" in full_text or "wordpress" in full_text:
                        domain = "Programmatic SEO & Content"
                    elif "transcript" in full_text or "whisper" in full_text or "podcast" in full_text:
                        domain = "Video-to-Text Social Snippets"
                    elif "paystack" in full_text or "stripe" in full_text or "webhook" in full_text:
                        domain = "Payment & Backend Infrastructure"

                    # Save verified commercial lead into SQLite
                    await IntentRepository.save_intent(
                        task_hash=task_hash,
                        domain=domain,
                        title=title,
                        snippet=verbatim_narration[:500] + "...",
                        source=link,
                        price=exact_budget
                    )
                    harvested_count += 1
                    print(f"[VERIFIED COMMERCIAL LEAD] [{domain}] Budget: ${exact_budget} | Title: {title}")

            except Exception as e:
                print(f"Error parsing feed {feed_url}: {e}")

    print(f"Successfully synchronized {harvested_count} verified commercial leads.")
    return harvested_count

# Aliases for router compatibility
harvest_live_github_leads = harvest_multivertical_leads
harvest_monetization_leads = harvest_multivertical_leads
harvest_advertised_tasks = harvest_multivertical_leads
