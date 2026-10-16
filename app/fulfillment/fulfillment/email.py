
import html
import logging
import re

import resend

from app.config import settings


logger = logging.getLogger(__name__)

# Configure the SDK once at module initialization.
if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY


def _render_report_html(
    task_id: str,
    tier: str,
    solution_content: str,
) -> str:
    """Render an HTML-safe report email."""
    safe_task_id = html.escape(task_id)
    safe_tier = html.escape(tier)

    # Escape source-derived content first, then preserve newlines.
    safe_content = html.escape(solution_content)
    safe_content = safe_content.replace("\n", "<br>\n")

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:600px;
        margin:0 auto;
        background:#0f172a;
        color:#f8fafc;
        padding:30px;
        border-radius:12px;
    ">
        <h2 style="color:#34d399;">
            SolveEase IntentForge
        </h2>

        <p>
            Your report is ready. Reference:
            <code>{safe_task_id}</code>
        </p>

        <p>Report tier: <strong>{safe_tier}</strong></p>

        <hr style="border-color:#334155;margin:20px 0;">

        <div style="
            background:#1e293b;
            padding:20px;
            border-radius:8px;
            font-size:14px;
            line-height:1.7;
            overflow-wrap:anywhere;
        ">
            {safe_content}
        </div>

        <p style="
            margin-top:30px;
            font-size:12px;
            color:#94a3b8;
        ">
            This report is based on the evidence described in its contents.
            Suggested fixes should be validated before production use.
        </p>
    </div>
    """


def send_fulfillment_email(
    to_email: str,
    task_id: str,
    tier: str,
    solution_content: str,
) -> bool:
    """
    Submit a report email to Resend.

    True means the provider accepted the request, not that final delivery
    to the recipient's inbox has been confirmed.
    """
    if not settings.RESEND_API_KEY:
        logger.error("Email dispatch unavailable: RESEND_API_KEY is missing.")
        return False

    sender = settings.RESEND_FROM_EMAIL
    if not sender:
        logger.error("Email dispatch unavailable: RESEND_FROM_EMAIL is missing.")
        return False

    if not isinstance(to_email, str):
        return False

    to_email = to_email.strip()

    # Basic format check; production should also validate purchase ownership.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_email):
        logger.warning("Email dispatch rejected: invalid recipient format.")
        return False

    if not isinstance(task_id, str) or not task_id.strip():
        return False

    if not isinstance(tier, str) or not tier.strip():
        return False

    if not isinstance(solution_content, str) or not solution_content.strip():
        return False

    try:
        response = resend.Emails.send({
            "from": sender,
            "to": [to_email],
            "subject": (
                f"Your SolveEase IntentForge report: {tier.strip()}"
            ),
            "html": _render_report_html(
                task_id.strip(),
                tier.strip(),
                solution_content,
            ),
        })

        # The SDK response normally contains an email ID on acceptance.
        # Avoid assuming acceptance equals delivery.
        if isinstance(response, dict):
            email_id = response.get("id")
        else:
            email_id = getattr(response, "id", None)

        if not email_id:
            logger.warning(
                "Email provider response did not contain an email ID."
            )
            return False

        logger.info(
            "Report email accepted by provider; task_id=%s email_id=%s",
            task_id,
            email_id,
        )
        return True

    except Exception:
        # Avoid logging credentials, recipient addresses, or report contents.
        logger.exception(
            "Email provider request failed; task_id=%s",
            task_id,
        )
        return False
