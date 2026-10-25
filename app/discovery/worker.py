import asyncio
from app.discovery.connectors import FeedScanner
from app.storage.repository import IntentRepository
from app.notifications.telegram import send_telegram_alert
from app.config import config

async def run_telemetry_sweep():
    # Ingests from Reddit, GitHub, Stack Overflow, Dev.to, and RSS Feeds
    live_leads = await FeedScanner.fetch_live_intents()
    new_count = 0
    
    for lead in live_leads:
        await IntentRepository.save_intent(
            task_hash=lead["task_hash"],
            domain=lead["domain"],
            title=lead["title"],
            snippet=lead["snippet"],
            source=lead["source"],
            price=lead["price"]
        )
        new_count += 1
        
        if lead["price"] >= 5.0:
            msg = f"🔥 <b>LIVE HIGH-VALUE INTENT SIGNAL (${lead['price']:.2f})</b>\n\n" \
                  f"<b>Domain:</b> {lead['domain']}\n" \
                  f"<b>Title:</b> {lead['title']}\n" \
                  f"<b>Source:</b> {lead['source']}"
            await send_telegram_alert(msg)
            
    return new_count

async def start_intent_daemon():
    while True:
        try:
            await run_telemetry_sweep()
        except Exception:
            pass
        await asyncio.sleep(config.SWEEP_INTERVAL_SECONDS)
