from fastapi import APIRouter, Request, HTTPException
from app.storage.repository import TransactionRepository, LedgerRepository
from app.services.playbook import generate_remediation_markdown
from app.services.mailer import send_playbook_email
import os
import hmac
import hashlib

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

@router.post("/webhook")
async def paystack_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    
    # Verify signature if secret key is present
    secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if secret_key:
        computed_sig = hmac.new(
            secret_key.encode('utf-8'),
            body,
            hashlib.sha512
        ).hexdigest()
        if not hmac.compare_digest(computed_sig, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

    event = await request.json()
    
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        reference = data.get("reference")
        email = data.get("customer", {}).get("email")
        gross_amount = data.get("amount", 0) / 100  # Convert from kobo to NGN/USD
        
        # Calculate standard gateway fee (e.g., 1.5% for Paystack local transactions)
        paystack_fee = (gross_amount * 0.015)
        net_balance = gross_amount - paystack_fee

        metadata = data.get("metadata", {})
        custom_fields = metadata.get("custom_fields", [])
        task_hash = ""
        issue_title = "Production Remediation Patch"
        
        for field in custom_fields:
            if field.get("variable_name") == "task_hash":
                task_hash = field.get("value")
            if field.get("variable_name") == "issue_title":
                issue_title = field.get("value")

        # 1. Log raw transaction
        await TransactionRepository.log_transaction(
            reference=reference,
            task_hash=task_hash,
            email=email,
            amount=gross_amount,
            status="SUCCESS"
        )

        # 2. Log entry into internal holding ledger
        await LedgerRepository.log_ledger_entry(
            reference=reference,
            email=email,
            gross_amount=gross_amount,
            fee=round(paystack_fee, 2),
            net_balance=round(net_balance, 2)
        )

        # 3. Generate markdown playbook content & dispatch email
        playbook_text = generate_remediation_markdown(
            title=issue_title,
            domain="Backend Concurrency & Reliability",
            snippet="Purchased via automated IntentForge telemetry feed.",
            source="https://solveease-intentforge.onrender.com"
        )

        await send_playbook_email(
            to_email=email,
            title=issue_title,
            markdown_content=playbook_text
        )

    return {"status": "received"}

@router.get("/ledger/summary")
async def get_ledger_summary():
    summary = await LedgerRepository.get_ledger_summary()
    entries = await LedgerRepository.get_all_ledger_entries()
    return {
        "status": "success",
        "summary": summary,
        "transactions": entries
    }
