
import html
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = 20.0


def send_fulfillment_email(
    to_email: str,
    task_id: str,
    tier: str,
    solution_content: str,
) -> bool:
    """
    Submit a purchased report to Resend.

    Returns True only when Resend accepts the request and returns
    an email ID. Acceptance does not guarantee inbox delivery.
    """
    api_key = getattr(settings, "RESEND_API_KEY", None)
    from_email = getattr(settings, "RESEND_FROM_EMAIL", None)

    if isinstance(api_key, bytes):
        api_key = api_key.decode("utf-8")

    if not api_key or not from_email:
        logger.error("Email fulfillment is not configured")
        return False

    safe_task_id = html.escape(str(task_id))
    safe_tier = html.escape(str(tier))
    safe_content = html.escape(str(solution_content))

    # Preserve line breaks while escaping all untrusted report content.
    safe_content = safe_content.replace("\n", "<br>\n")

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": f"SolveEase report: {tier} — {task_id}",
        "text": (
            f"SolveEase {tier}\n"
            f"Report ID: {task_id}\n\n"
            f"{solution_content}\n\n"
            "This report provides diagnostic guidance and does not "
            "guarantee that a technical issue has been resolved."
        ),
        "html": (
            "<div style='font-family:Arial,sans-serif;"
            "max-width:700px;margin:auto;line-height:1.6'>"
            "<h2>SolveEase IntentForge</h2>"
            f"<p><strong>Report:</strong> {safe_task_id}</p>"
            f"<p><strong>Type:</strong> {safe_tier}</p>"
            "<hr>"
            f"<div>{safe_content}</div>"
            "<hr>"
            "<p><small>This report provides diagnostic guidance. "
            "It does not guarantee that a technical issue has "
            "been resolved.</small></p>"
            "</div>"
        ),
    }

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=RESEND_TIMEOUT,
        )

        if response.status_code not in (200, 201):
            logger.error(
                "Resend rejected a fulfillment request; HTTP %s",
                response.status_code,
            )
            return False

        result = response.json()
        if not isinstance(result, dict) or not result.get("id"):
            logger.error("Resend returned no email ID")
            return False

        logger.info(
            "Resend accepted fulfillment for report %s",
            task_id,
        )
        return True

    except (httpx.HTTPError, ValueError):
        logger.exception("Email fulfillment request failed")
        return False
