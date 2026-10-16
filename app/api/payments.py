
import hashlib
import hmac
import logging
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.storage.database import db_connection
from app.storage.repository import IntentRepository

router = APIRouter()
logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_CURRENCY = os.getenv("PAYSTACK_CURRENCY", "NGN").strip().upper()
PAYSTACK_TIMEOUT = 20.0

PRICE_TABLE = {
    "brief": int(os.getenv("INTENTFORGE_BRIEF_AMOUNT", "100")),
    "playbook": int(os.getenv("INTENTFORGE_PLAYBOOK_AMOUNT", "300")),
}

TIER_ALIASES = {
    "brief": "brief",
    "problem brief": "brief",
    "technical playbook": "playbook",
    "playbook": "playbook",
}

DISPLAY_TIERS = {
    "brief": "Problem Brief",
    "playbook": "Technical Playbook",
}


class InitializePaymentRequest(BaseModel):
    email: EmailStr
    task_id: str = Field(min_length=1, max_length=100)
    tier: str = Field(min_length=1, max_length=50)


def _secret_key() -> str:
    value = settings.PAYSTACK_SECRET_KEY
    if not value or value.startswith("sk_live_your_"):
        raise HTTPException(
            status_code=503,
            detail="Payment service is not configured",
        )
    return value


def _normalize_tier(tier: str) -> str:
    normalized = TIER_ALIASES.get(tier.strip().lower())
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid report tier")
    return normalized


def _price_for_tier(tier: str) -> int:
    amount = PRICE_TABLE[tier]
    if amount <= 0:
        raise HTTPException(
            status_code=503,
            detail="Payment pricing is incorrectly configured",
        )
    return amount


async def _paystack_get(path: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=PAYSTACK_TIMEOUT) as client:
            response = await client.get(
                f"{PAYSTACK_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {_secret_key()}"},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Paystack verification request failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to verify payment with the payment provider",
        )

    if not isinstance(result, dict) or result.get("status") is not True:
        raise HTTPException(
            status_code=502,
            detail="Payment provider could not verify the transaction",
        )

    return result


@router.post("/api/v1/payment/initialize")
async def initialize_payment(payload: InitializePaymentRequest):
    tier = _normalize_tier(payload.tier)
    amount = _price_for_tier(tier)

    task = IntentRepository.get_task_by_id(payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if task.get("action") != "published":
        raise HTTPException(
            status_code=409,
            detail="This report is not available for purchase",
        )

    request_data = {
        "email": str(payload.email),
        "amount": amount,
        "currency": PAYSTACK_CURRENCY,
        "callback_url": f"{settings.WEB_APP_URL}/payment/callback",
        "metadata": {
            "task_id": payload.task_id,
            "tier": tier,
            "custom_fields": [{
                "display_name": "Report",
                "variable_name": "report",
                "value": payload.task_id,
            }],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=PAYSTACK_TIMEOUT) as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {_secret_key()}",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Paystack initialization failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to initialize payment",
        )

    if not isinstance(result, dict) or result.get("status") is not True:
        raise HTTPException(
            status_code=502,
            detail="Payment provider returned an invalid response",
        )

    data = result.get("data")
    if (
        not isinstance(data, dict)
        or not data.get("authorization_url")
        or not data.get("reference")
    ):
        raise HTTPException(
            status_code=502,
            detail="Payment provider returned an invalid response",
        )

    return {
        "status": "success",
        "authorization_url": data["authorization_url"],
        "reference": data["reference"],
        "amount": amount,
        "currency": PAYSTACK_CURRENCY,
        "tier": DISPLAY_TIERS[tier],
    }


@router.post("/api/v1/payment/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
):
    body = await request.body()
    secret = _secret_key()

    if not x_paystack_signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_paystack_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        event = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not isinstance(event, dict) or event.get("event") != "charge.success":
        return {"status": "ignored"}

    event_data = event.get("data")
    if not isinstance(event_data, dict):
        raise HTTPException(status_code=400, detail="Invalid event data")

    reference = event_data.get("reference")
    if not isinstance(reference, str) or not reference.strip():
        raise HTTPException(status_code=400, detail="Missing transaction reference")

    verified = await _paystack_get(
        f"/transaction/verify/{reference}"
    )
    payment = verified.get("data")

    if not isinstance(payment, dict) or payment.get("status") != "success":
        raise HTTPException(status_code=400, detail="Payment is not successful")

    if payment.get("reference") != reference:
        raise HTTPException(status_code=400, detail="Reference mismatch")

    if str(payment.get("currency", "")).upper() != PAYSTACK_CURRENCY:
        raise HTTPException(status_code=400, detail="Currency mismatch")

    try:
        paid_amount = int(payment.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    metadata = payment.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="Invalid payment metadata")

    task_id = metadata.get("task_id")
    tier_value = metadata.get("tier")
    if not isinstance(task_id, str) or not isinstance(tier_value, str):
        raise HTTPException(status_code=400, detail="Missing purchase metadata")

    tier = _normalize_tier(tier_value)
    expected_amount = _price_for_tier(tier)

    if paid_amount != expected_amount:
        raise HTTPException(status_code=400, detail="Payment amount mismatch")

    customer = payment.get("customer") or {}
    email = customer.get("email") if isinstance(customer, dict) else None
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(status_code=400, detail="Missing customer email")

    task = IntentRepository.get_task_by_id(task_id)
    if task is None or task.get("action") != "published":
        raise HTTPException(status_code=400, detail="Report is unavailable")

    if not isinstance(task.get("raw_signal"), str) or not task["raw_signal"].strip():
        raise HTTPException(status_code=500, detail="Report content is unavailable")

    now = int(time.time())
    tier_name = DISPLAY_TIERS[tier]

    # Record the verified payment and queue its fulfillment atomically.
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO verified_payments (
                reference, task_id, customer_email, tier, amount,
                currency, status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
            ON CONFLICT (reference) DO NOTHING;
        """, (
            reference, task_id, email, tier, paid_amount,
            PAYSTACK_CURRENCY, now, now,
        ))

        existing = conn.execute("""
            SELECT task_id, customer_email, tier, amount, currency, status
            FROM verified_payments
            WHERE reference = %s
            FOR UPDATE;
        """, (reference,)).fetchone()

        if existing is None:
            raise HTTPException(status_code=500, detail="Payment ledger unavailable")

        if (
            existing["task_id"] != task_id
            or existing["customer_email"].lower() != email.lower()
            or existing["tier"] != tier
            or int(existing["amount"]) != paid_amount
            or existing["currency"] != PAYSTACK_CURRENCY
        ):
            raise HTTPException(
                status_code=409,
                detail="Payment reference does not match this purchase",
            )

        if existing["status"] == "sent":
            return {
                "status": "success",
                "unlocked": True,
                "duplicate": True,
            }

        conn.execute("""
            INSERT INTO fulfillment_jobs (
                task_id, purchase_reference, recipient_email, tier,
                status, attempts, next_attempt_at, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, 'pending', 0, NOW(), NOW(), NOW())
            ON CONFLICT (purchase_reference) DO NOTHING;
        """, (task_id, reference, email, tier_name))

    return {
        "status": "success",
        "verified": True,
        "queued": True,
        "reference": reference,
    }
