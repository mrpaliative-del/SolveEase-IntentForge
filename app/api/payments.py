import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.config import config
from app.storage.repository import TransactionRepository
from app.fulfillment.email import send_playbook_email
from app.fulfillment.playbooks import generate_dynamic_playbook

router = APIRouter(prefix="/api/v1/payment")

@router.post("/webhook")
async def paystack_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if config.PAYSTACK_SECRET_KEY:
        computed_hash = hmac.new(
            config.PAYSTACK_SECRET_KEY.encode('utf-8'),
            body,
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, signature):
            raise HTTPException(status_code=400, detail="Invalid HMAC signature")

    payload = await request.json()
    event_type = payload.get("event")

    if event_type == "charge.success":
        data = payload.get("data", {})
        reference = data.get("reference", "")
        amount = data.get("amount", 0) / 100.0
        customer_email = data.get("customer", {}).get("email", "")
        metadata = data.get("metadata", {})

        playbook_title = metadata.get("playbook_title", "Technical Architecture Resolution")
        domain = metadata.get("domain", "General System Engineering")
        snippet = metadata.get("snippet", "Captured production telemetry issue.")
        playbook_id = metadata.get("playbook_id", "pb_auto_generated")

        await TransactionRepository.save_transaction(
            reference=reference,
            email=customer_email,
            amount=amount,
            status="success",
            playbook_id=playbook_id
        )

        playbook_content = generate_dynamic_playbook(playbook_title, domain, snippet)
        success, res_msg = await send_playbook_email(customer_email, playbook_title, playbook_content)

        return JSONResponse(status_code=200, content={
            "status": "fulfilled" if success else "email_failed",
            "reference": reference,
            "details": res_msg
        })

    return JSONResponse(status_code=200, content={"status": "ignored_event"})
