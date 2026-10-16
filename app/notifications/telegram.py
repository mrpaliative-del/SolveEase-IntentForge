
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TIMEOUT = httpx.Timeout(8.0, connect=3.0)
TELEGRAM_MAX_MESSAGE_LENGTH = 4000


def _split_message(message: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH):
    """Split long messages without silently discarding content."""
    if len(message) <= limit:
        return [message]

    chunks = []
    remaining = message

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")

    return chunks


async def send_telegram_alert(
    message: str,
    *,
    parse_mode: Optional[str] = None,
) -> bool:
    """
    Send an alert to the configured Telegram chat.

    Returns True only if Telegram confirms every message chunk.
    Returns False if configuration is missing or delivery fails.

    Use plain text by default. If parse_mode is supplied, ensure the
    message is correctly escaped for that Telegram formatting mode.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("Telegram alerts disabled: credentials not configured.")
        return False

    if not isinstance(message, str) or not message.strip():
        logger.warning("Telegram alert skipped: message is empty or invalid.")
        return False

    if parse_mode not in (None, "Markdown", "MarkdownV2", "HTML"):
        logger.warning("Telegram alert skipped: unsupported parse mode.")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    chunks = _split_message(message)

    try:
        async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT) as client:
            for chunk in chunks:
                payload = {
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                }

                if parse_mode:
                    payload["parse_mode"] = parse_mode

                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                if not result.get("ok", False):
                    logger.warning(
                        "Telegram rejected an alert: %s",
                        result.get("description", "No error description"),
                    )
                    return False

        return True

    except httpx.TimeoutException:
        logger.warning("Telegram alert timed out.")
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Telegram returned HTTP status %s.",
            exc.response.status_code,
        )
    except (httpx.RequestError, ValueError):
        logger.exception("Telegram alert request failed.")
    except Exception:
        logger.exception("Unexpected Telegram alert error.")

    return False
