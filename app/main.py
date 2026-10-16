
import asyncio
import hashlib
import html
import logging
import re
import time
from collections import Counter
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
    "shopify", "ecommerce", "SEO",
    "affiliatemarketing", "woocommerce", "webdev",
]
RSS_FEEDS = [
    ("https://www.searchenginejournal.com/feed/", "Search Engine Journal"),
    ("https://www.shopify.com/blog/rss.xml", "Shopify Blog"),
    ("https://dev.to/feed", "Dev.to Community"),
]

# Require evidence of a specific obstacle near the beginning.
PROBLEM_RE = re.compile(
    r"\b(?:"
    r"not working|doesn't work|does not work|"
    r"stopped working|broken|blocked|failed|failing|"
    r"can't|cannot|unable to|keeps failing|"
    r"error(?:\s+code)?|exception|traceback|"
    r"bug|malfunction|timed out|timeout|"
    r"not indexing|deindexed|disapproved|suspended|"
    r"checkout fails|payment failed|"
    r"webhook not firing|tracking not working|"
    r"won't load|will not load|crashes|crashing|"
    r"need help fixing|how do i fix|"
    r"production issue|urgent fix"
    r")\b",
    re.IGNORECASE,
)

# Editorial titles often describe content rather than a buyer's problem.
EDITORIAL_RE = re.compile(
    r"\b(?:"
    r"vs\.?|comparison|review|tested \d+|"
    r"what .* actually means|"
    r"doesn't feel like the same|"
    r"i rebuilt .* because|"
    r"beginner'?s guide|ultimate guide|"
    r"tips and tricks|top \d+|"
    r"what is|everything you need to know"
    r")\b",
    re.IGNORECASE,
)


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _price_to_cents(value: Any) -> int:
    if isinstance(value, str):
        try:
            cents = Decimal(value.strip().replace("$", "")) * 100
        except InvalidOperation as exc:
            raise ValueError("Invalid taxonomy price.") from exc
    elif isinstance(value, (int, float, Decimal)):
        # Taxonomy price_cents values are already cents.
        cents = Decimal(str(value))
    else:
        raise ValueError("Unsupported taxonomy price format.")

    if cents != cents.to_integral_value():
        raise ValueError("Price must resolve to whole cents.")

    result = int(cents)
    if not 100 <= result <= 500:
        raise ValueError(f"Price outside allowed range: {result} cents.")
    return result


def _match_taxonomy(text: str) -> Optional[tuple[str, dict]]:
    for category, spec in MEGA_TAXONOMY.items():
        for pattern in spec.get("patterns", []):
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return category, spec
            except (TypeError, re.error):
                logger.warning("Invalid taxonomy pattern: %s", category)
    return None


def _stable_task_hash(payload: dict, text: str) -> str:
    source_id = payload.get("signal_id") or payload.get("url") or ""
    source = payload.get("source_type") or payload.get("source") or ""
    identity = (
        f"{str(source).strip().lower()}\n"
        f"{str(source_id).strip() if source_id else text.lower()}"
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

    text = _normalize_text(
        payload.get("text")
        or payload.get("content")
        or payload.get("description")
        or ""
    )
    title = _normalize_text(payload.get("title") or "")
    source = _normalize_text(payload.get("source"))

    if not text or not source:
        return None

    # Evaluate the title separately where the connector provides one.
    lead = title or text[:240]
    evidence_text = f"{lead} {text[:700]}"

    if EDITORIAL_RE.search(lead):
        return None

    if not PROBLEM_RE.search(evidence_text):
        return None

    if not is_actionable_intent(evidence_text):
        return None

    matched = _match_taxonomy(evidence_text)
    if matched is None:
        return None

    category, spec = matched

    try:
        price_cents = _price_to_cents(spec.get("price_cents"))
    except (ValueError, InvalidOperation) as exc:
        logger.warning(
            "Invalid price for %s: %r (%s)",
            category, spec.get("price_cents"), exc,
        )
        return None

    task_hash = _stable_task_hash(payload, text)
    task_id = f"IF-{task_hash[:24]}"

    record = (
        task_hash,
        task_id,
        _source_timestamp(payload),
        source[:200],
        str(category)[:100],
        text[:3000],
        price_cents,
        "pending",
    )

    try:
        saved = IntentRepository.save_task(record)
    except Exception:
        logger.exception("Candidate persistence failed.")
        return None

    if not saved:
        return None

    return {
        "task_id": task_id,
        "category": category,
        "price_cents": price_cents,
        "source": source,
        "summary": lead[:140],
    }


async def _fetch_all_sources(
    client: httpx.AsyncClient,
) -> list[dict]:
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
                "Source collector failed: %s",
                type(result).__name__,
            )
        elif isinstance(result, list):
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
    rejected = Counter()

    for payload in raw_signals:
        try:
            candidate = await asyncio.to_thread(
                _process_signal, payload
            )
        except Exception:
            logger.exception("Signal processing failed.")
            rejected["processing_error"] += 1
            continue

        if candidate:
            newly_added.append(candidate)
        else:
            rejected["filtered_or_duplicate"] += 1

    try:
        total_count = await asyncio.to_thread(
            IntentRepository.get_total_count
        )
    except Exception:
        logger.exception("Database count failed.")
        total_count = None

    duration = round(time.monotonic() - started, 2)

    logger.info(
        "Sweep complete: fetched=%d accepted=%d rejected=%d "
        "total=%s duration=%ss rejection_breakdown=%s",
        len(raw_signals),
        len(newly_added),
        sum(rejected.values()),
        total_count if total_count is not None else "unavailable",
        duration,
        dict(rejected),
    )

    if newly_added:
        lines = [
            "SolveEase IntentForge — new problem candidates", ""
        ]

        for item in newly_added[:MAX_ALERT_SNIPPETS]:
            lines.append(
                f"- {item['category']} | "
                f"{item['price_cents']} cents | {item['task_id']}"
            )
            lines.append(f"  {item['summary']}")

        if len(newly_added) > MAX_ALERT_SNIPPETS:
            lines.append(
                f"...and {len(newly_added) - MAX_ALERT_SNIPPETS} more."
            )

        lines.extend([
            "",
            f"New candidates: {len(newly_added)}",
            f"Total stored records: {total_count}",
            "Status: candidates only; demand is unverified.",
        ])

        try:
            sent = await send_telegram_alert("\n".join(lines))
            if not sent:
                logger.warning("Telegram alert was not confirmed.")
        except Exception:
            logger.exception("Telegram notification failed.")

    return {
        "fetched": len(raw_signals),
        "new_candidates": len(newly_added),
        "rejected": sum(rejected.values()),
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
    while True:
        try:
            worked = await asyncio.to_thread(
                process_next_fulfillment_job
            )
            if not worked:
                await asyncio.sleep(FULFILLMENT_IDLE_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Fulfillment worker failed.")
            await asyncio.sleep(FULFILLMENT_IDLE_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version="1.2.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(inbound.router)
app.include_router(payments.router)
