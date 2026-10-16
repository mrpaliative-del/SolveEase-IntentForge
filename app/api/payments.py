
import hashlib
import hmac
import logging
import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.storage.database import db_connection
from app.storage.repository import IntentRepository
from app.fulfillment.worker import (
    enqueue_fulfillment,
    init_fulfillment_queue,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PAYSTACK_API = "https://api.paystack.co"
PAYSTACK_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Configure these amounts in Paystack's smallest currency unit.
# Examples: NGN uses kobo; USD uses cents.
PAYMENT_CURRENCY = os.getenv("PAYSTACK_CURRENCY", "").strip().upper()

PRICE_TABLE = {
    "brief": {
        "tier": "Brief",
        "amount": os.getenv("INTENTFORGE_BRIEF_AMOUNT", ""),
    },
    "playbook": {
        "tier": "Technical Playbook",
        "amount": os.getenv("INTENTFORGE_PLAYBOOK_AMOUNT", ""),
    },
}


class InitializePaymentRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    task_id: str = Field(min_length=1, max_length=200)
    tier: str = Field(min_length=1, max_length=80)


def _secret_key() -> str:
    """Support settings configured with either str or bytes."""
    value = settings.PAYSTACK_SECRET_KEY
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value.strip() if value else ""


def _get_tier(tier: str) -> dict:
    normalized = tier.strip().lower()

    if normalized in ("brief", "concise problem brief"):
        key = "brief"
    elif normalized in (
        "technical playbook",
        "premium technical playbook",
        "playbook",
    ):
        key = "playbook"
    else:
        raise HTTPException(status_code=400, detail="Unsupported report tier.")

    configured = PRICE_TABLE[key]

    try:
        amount = int(configured["amount"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=503,
            detail="Payment pricing is not configured.",
        )

    if amount <= 0 or not PAYMENT_CURRENCY:
        raise HTTPException(
            status_code=503,
            detail="Payment pricing or currency is not configured.",
        )

    return {
        "tier": configured["tier"],
        "amount": amount,
        "currency": PAYMENT_CURRENCY,
    }


def _init_payment_ledger() -> None:
    with db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verified_payments (
                reference TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                tier TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'verified',
                created_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
            );
        """)


def _record_verified_payment(
    reference: str,
    task_id: str,
    email: str,
    tier: str,
    amount: int,
    currency: str,
) -> None:
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO verified_payments (
                reference, task_id, customer_email,
                tier, amount, currency, payment_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'verified')
            ON CONFLICT(reference) DO NOTHING;
        """, (reference, task_id, email, tier, amount, currency))


async def _verify_with_paystack(reference: str) -> dict:
    key = _secret_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Payment verification is not configured.",
        )

    url = f"{PAYSTACK_API}/transaction/verify/{quote(reference, safe='')}"

    try:
        async with httpx.AsyncClient(timeout=PAYSTACK_TIMEOUT) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {key}"},
            )
            response.raise_for_status()
            result = response.json()

        if not result.get("status") or not isinstance(result.get("data"), dict):
            raise HTTPException(
                status_code=502,
                detail="Payment provider could not verify the transaction.",
            )

        return result["data"]

    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError):
        logger.exception("Paystack transaction verification failed.")
        raise HTTPException(
            status_code=502,
            detail="Payment verification is temporarily unavailable.",
        )


@router.post("/api/v1/payment/initialize")
async def initialize_payment(payload: InitializePaymentRequest):
    key = _secret_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Payment initialization is not configured.",
        )

    # Never accept price or product tier pricing from the client.
    product = _get_tier(payload.tier)

    task = IntentRepository.get_task_by_id(payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Report not found.")

    # This API expects the refined repository's dictionary/Row result.
    task = dict(task)
    if task.get("action") != "published":
        raise HTTPException(
            status_code=404,
            detail="This report is not currently available for purchase.",
        )

    if not settings.WEB_APP_URL:
        raise HTTPException(
            status_code=503,
            detail="Payment callback URL is not configured.",
        )

    request_data = {
        "email": payload.email.strip(),
        "amount": product["amount"],
        "currency": product["currency"],
        "callback_url": (
            f"{settings.WEB_APP_URL.rstrip('/')}/payment/callback"
        ),
        "metadata": {
            "task_id": payload.task_id,
            "tier": product["tier"],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=PAYSTACK_TIMEOUT) as client:
            response = await client.post(
                f"{PAYSTACK_API}/transaction/initialize",
                json=request_data,
                headers={"Authorization": f"Bearer {key}"},
            )
            response.raise_for_status()
            result = response.json()

        data = result.get("data") or {}
        if not result.get("status") or not data.get("authorization_url") or not data.get("reference"):
            raise HTTPException(
                status_code=502,
                detail="Payment provider did not initialize the transaction.",
            )

        return {
            "status": "success",
            "authorization_url": data["authorization_url"],
            "reference": data["reference"],
            "amount": product["amount"],
            "currency": product["currency"],
            "tier": product["tier"],
        }

    except HTTPException:
        raise
    except httpx.HTTPError:
        logger.exception("Paystack initialization failed.")
        raise HTTPException(
            status_code=502,
            detail="Payment initialization is temporarily unavailable.",
        )


@router.post("/api/v1/payment/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
):
    key = _secret_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Webhook verification is not configured.",
        )

    body = await request.body()

    if not x_paystack_signature:
        raise HTTPException(status_code=400, detail="Missing signature.")

    expected = hmac.new(
        key.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(expected, x_paystack_signature):
        raise HTTPException(status_code=403, detail="Invalid signature.")

    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.")

    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    event_data = event.get("data") or {}
    reference = event_data.get("reference")

    if not isinstance(reference, str) or not reference.strip():
        raise HTTPException(status_code=400, detail="Missing payment reference.")

    # Verify independently with Paystack; never rely on the webhook payload
    # alone for the final payment status.
    transaction = await _verify_with_paystack(reference.strip())

    if transaction.get("status") != "success":
        return {"status": "payment_not_successful"}

    metadata = transaction.get("metadata") or {}
    task_id = metadata.get("task_id")
    requested_tier = metadata.get("tier")

    if not isinstance(task_id, str) or not task_id.strip():
        raise HTTPException(status_code=400, detail="Missing task metadata.")

    product = _get_tier(requested_tier or "")

    if transaction.get("amount") != product["amount"]:
        raise HTTPException(status_code=400, detail="Payment amount mismatch.")

    if str(transaction.get("currency", "")).upper() != product["currency"]:
        raise HTTPException(status_code=400, detail="Payment currency mismatch.")

    customer = transaction.get("customer") or {}
    email = customer.get("email")

    if not isinstance(email, str) or not email.strip():
        raise HTTPException(status_code=400, detail="Missing customer email.")

    task = IntentRepository.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=400, detail="Referenced report not found.")

    # Prepare durable storage before acknowledging the webhook.
    _init_payment_ledger()
    init_fulfillment_queue()

    _record_verified_payment(
        reference=reference,
        task_id=task_id,
        email=email.strip(),
        tier=product["tier"],
        amount=product["amount"],
        currency=product["currency"],
    )

    # The queue's unique purchase_reference prevents duplicate jobs when
    # Paystack retries the same webhook.
    enqueue_fulfillment(
        task_id=task_id,
        purchase_reference=reference,
        recipient_email=email.strip(),
        tier=product["tier"],
    )

    return {"status": "success", "fulfillment": "queued"}
