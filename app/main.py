
import asyncio
import hashlib
import logging
import re
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx
from fastapi import FastAPI

from app.api import health, inbound, payments
from app.discovery.connectors import (
    fetch_github_issues_deep,
    fetch_reddit_json,
    fetch_rss_feed,
)
from app.discovery.filters import is_actionable_intent
from app.discovery.taxonomy import MEGA_TAXONOMY
from app.fulfillment.worker import (
    init_fulfillment_queue,
    process_next_fulfillment_job,
)
from app.notifications.telegram import send_telegram_alert
from app.storage.database import init_db
from app.storage.repository import IntentRepository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("solveease.intentforge")

SWEEP_INTERVAL_SECONDS = 1800
INITIAL_DELAY_SECONDS = 15
MAX_ALERT_SNIPPETS = 5
FULFILLMENT_IDLE_SECONDS = 10

SUBREDDITS = [
    "shopify",
    "ecommerce",
    "SEO",
    "affiliatemarketing",
    "woocommerce",
    "webdev",
]

RSS_FEEDS = [
    ("https://www.searchenginejournal.com/feed/", "Search Engine Journal"),
    ("https://www.shopify.com/blog/rss.xml", "Shopify Blog"),
    ("https://dev.to/feed", "Dev.to Community"),
]


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _price_to_cents(value: Any) -> int:
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").strip()
        try:
            amount = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError("Invalid taxonomy price.") from exc
        cents = amount * 100

    elif isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
        if amount == amount.to_integral_value() and 100 <= amount <= 500:
            cents = amount
        else:
            cents = amount * 100
    else:
        raise ValueError("Unsupported taxonomy price format.")

    if cents != cents.to_integral_value():
        raise ValueError("Price must resolve to a whole number of cents.")

    result = int(cents)
    if not 100 <= result <= 500:
        raise ValueError(
            f"Taxonomy price must be between 100 and 500 cents; got {result}."
        )
    return result


def _match_taxonomy(signal_text: str) -> Optional[tuple[str, dict]]:
    for category, spec in MEGA_TAXONOMY.items():
        for pattern in spec.get("patterns", []):
            try:
                if re.search(pattern, signal_text, flags=re.IGNORECASE):
                    return category, spec
            except (TypeError, re.error):
                logger.warning(
                    "Skipping invalid taxonomy pattern in category %s.",
                    category,
                )
    return None


def _stable_task_hash(payload: dict, normalized_text: str) -> str:
    source_id = payload.get("signal_id") or payload.get("url") or ""
    source_type = payload.get("source_type") or payload.get("source") or ""
    identity = (
        f"{str(source_type).strip().lower()}\n"
        f"{str(source_id).strip() if source_id else normalized_text.lower()}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _source_timestamp(payload: dict) -> str:
    value = payload.get("timestamp")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return datetime.now(timezone.utc).isoformat()


def _process_signal(payload: dict) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None

    signal_text = _normalize_text(payload.get("text"))
    source = _normalize_text(payload.get("source"))

    if not signal_text or not source:
        return None
    if not is_actionable_intent(signal_text):
        return None

    matched = _match_taxonomy(signal_text)
    if matched is None:
        return None

    category, spec = matched
    try:
        price_cents = _price_to_cents(spec.get("price"))
    except ValueError:
        logger.warning(
            "Skipping category %s because its price is invalid.", category
        )
        return None

    task_hash = _stable_task_hash(payload, signal_text)
    task_id = f"IF-{task_hash[:24]}"

    record = (
        task_hash,
        task_id,
        _source_timestamp(payload),
        source[:200],
        str(category)[:100],
        signal_text[:3000],
        price_cents,
        "pending",
    )

    try:
        saved = IntentRepository.save_task(record)
    except Exception:
        logger.exception("Failed to persist a discovered candidate.")
        return None

    if not saved:
        return None

    return {
        "task_id": task_id,
        "category": category,
        "price_cents": price_cents,
        "source": source,
        "summary": signal_text[:140],
    }


async def _fetch_all_sources(client: httpx.AsyncClient) -> list[dict]:
    tasks = [
        fetch_reddit_json(client, subreddit)
        for subreddit in SUBREDDITS
    ]
    tasks.extend(
        fetch_rss_feed(client, url, name)
        for url, name in RSS_FEEDS
    )
    tasks.append(fetch_github_issues_deep(client))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    collected = []

    for result in results:
        if isinstance(result, BaseException):
            if isinstance(result, asyncio.CancelledError):
                raise result
            logger.warning(
                "A source collector failed: %s", type(result).__name__
            )
            continue
        if isinstance(result, list):
            collected.extend(
                item for item in result if isinstance(item, dict)
            )

    return collected


async def run_telemetry_sweep() -> dict:
    started = time.monotonic()
    timeout = httpx.Timeout(12.0, connect=5.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": "SolveEase-IntentForge/1.0"},
    ) as client:
        raw_signals = await _fetch_all_sources(client)

    newly_added = []
    for payload in raw_signals:
        try:
            candidate = await asyncio.to_thread(_process_signal, payload)
        except Exception:
            logger.exception("Unexpected signal processing failure.")
            continue
        if candidate:
            newly_added.append(candidate)

    try:
        total_count = await asyncio.to_thread(
            IntentRepository.get_total_count
        )
    except Exception:
        logger.exception("Unable to retrieve the database count.")
        total_count = None

    duration = round(time.monotonic() - started, 2)
    logger.info(
        "Sweep complete: fetched=%d new_candidates=%d total=%s duration=%ss",
        len(raw_signals),
        len(newly_added),
        total_count if total_count is not None else "unavailable",
        duration,
    )

    if newly_added:
        lines = ["SolveEase IntentForge — new problem candidates", ""]

        for item in newly_added[:MAX_ALERT_SNIPPETS]:
            lines.append(
                f"- {item['category']} | {item['price_cents']} cents "
                f"| {item['task_id']}"
            )
            lines.append(f"  {item['summary']}")

        if len(newly_added) > MAX_ALERT_SNIPPETS:
            lines.append(
                f"...and {len(newly_added) - MAX_ALERT_SNIPPETS} more candidates."
            )

        lines.extend([
            "",
            f"New candidates: {len(newly_added)}",
            f"Total stored records: {total_count if total_count is not None else 'unavailable'}",
            "Status: candidates only; not verified demand or completed fixes.",
        ])

        try:
            sent = await send_telegram_alert("\n".join(lines))
            if not sent:
                logger.warning("Telegram did not confirm the alert.")
        except Exception:
            logger.exception("Telegram notification failed.")

    return {
        "fetched": len(raw_signals),
        "new_candidates": len(newly_added),
        "total_stored": total_count,
        "duration_seconds": duration,
    }


async def background_telemetry_loop() -> None:
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    while True:
        try:
            await run_telemetry_sweep()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telemetry sweep failed.")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


async def background_fulfillment_loop() -> None:
    """Continuously process verified purchases from the durable queue."""
    while True:
        try:
            worked = await asyncio.to_thread(process_next_fulfillment_job)
            if not worked:
                await asyncio.sleep(FULFILLMENT_IDLE_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Fulfillment worker loop failed.")
            await asyncio.sleep(FULFILLMENT_IDLE_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail startup clearly if Neon is unavailable or misconfigured.
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(init_fulfillment_queue)

    telemetry_task = asyncio.create_task(
        background_telemetry_loop(),
        name="intentforge-telemetry",
    )
    fulfillment_task = asyncio.create_task(
        background_fulfillment_loop(),
        name="intentforge-fulfillment",
    )

    app.state.telemetry_task = telemetry_task
    app.state.fulfillment_task = fulfillment_task

    try:
        yield
    finally:
        telemetry_task.cancel()
        fulfillment_task.cancel()
        with suppress(asyncio.CancelledError):
            await telemetry_task
        with suppress(asyncio.CancelledError):
            await fulfillment_task


app = FastAPI(
    title="SolveEase IntentForge",
    description="Public problem discovery and report fulfillment service.",
    version="1.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(inbound.router)
app.include_router(payments.router)
