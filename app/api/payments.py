from fastapi import APIRouter, Request, HTTPException
from app.storage.repository import TransactionRepository, LedgerRepository
import os
import hmac
import hashlib
import httpx

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

def generate_remediation_markdown(title: str, domain: str, snippet: str, source: str) -> str:
    return (
        f"# SolveEase IntentForge Remediation Patch\n\n"
        f"**Target Issue:** {title}\n\n"
        f"**Domain:** {domain}\n\n"
        f"**Original Source:** {source}\n\n"
        f"---\n\n"
        f"## Root-Cause Analysis\n\n"
        f"Based on telemetry captured from public developer engineering channels, this bottleneck typically stems from unhandled asynchronous execution constraints, state synchronization gaps, or strict gateway timeout profiles.\n\n"
        f"**Context / Issue Snippet:**\n"
        f"> \"{snippet}\"\n\n"
        f"---\n\n"
        f"## Step-by-Step Production Patch\n\n"
        f"### 1. Architectural Guardrail Implementation\n\n"
        f"To eliminate latency spikes and prevent request blocking under high load, isolate synchronous operations or external network calls into dedicated background threads or worker queues:\n\n"
        f"```python\n"
        f"import asyncio\n"
        f"from concurrent.futures import ThreadPoolExecutor\n\n"
        f"executor = ThreadPoolExecutor(max_workers=4)\n\n"
        f"async def execute_isolated_task(payload: dict):\n"
        f"    loop = asyncio.get_running_loop()\n"
        f"    return await loop.run_in_executor(executor, blocking_third_party_call, payload)\n"
        f"```\n\n"
        f"### 2. Idempotency & Error Handling\n\n"
        f"Ensure your service handles duplicate requests or webhook retries gracefully using atomic database locks or unique task hashes to avoid race conditions.\n\n"
        f"### 3. Verification & Monitoring\n\n"
        f"* Monitor event loop lag using standard APM telemetry.\n"
        f"* Configure automated alerts for any HTTP 5xx or gateway timeout anomalies.\n\n"
        f"---\n\n"
        f"*Generated autonomously by SolveEase IntentForge v3.0.*\n"
    )

async def send_playbook_email(to_email: str, title: str, markdown_content: str):
    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        print("RESEND_API_KEY not configured. Skipping email dispatch.")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": "IntentForge Playbooks <playbooks@solveease.com>",
        "to": [to_email],
        "subject": f"Your Remediation Patch: {title}",
        "text": f"Thank you for your purchase!\n\nHere is your requested remediation playbook:\n\n{markdown_content}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            print(f"Playbook successfully dispatched to {to_email}")
            return True
        else:
            print(f"Failed to send email: {response.text}")
            return False

@router.post("/webhook")
async def paystack_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    
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
        gross_amount = data.get("amount", 0) / 100  # Convert from kobo
        
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

        # 1. Log transaction
        await TransactionRepository.log_transaction(
            reference=reference,
            task_hash=task_hash,
            email=email,
            amount=gross_amount,
            status="SUCCESS"
        )

        # 2. Log into internal ledger
        await LedgerRepository.log_ledger_entry(
            reference=reference,
            email=email,
            gross_amount=gross_amount,
            fee=round(paystack_fee, 2),
            net_balance=round(net_balance, 2)
        )

        # 3. Generate markdown & dispatch email
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
