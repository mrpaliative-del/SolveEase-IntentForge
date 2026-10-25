import httpx
from app.config import config

async def send_playbook_email(to_email: str, playbook_title: str, playbook_content: str):
    if not config.RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"
        
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 8px;">
        <h2 style="color: #1a1a1a;">🛠️ SolveEase Technical Playbook</h2>
        <p style="color: #4a4a4a;">Thank you for your purchase. Below is your instant technical remediation brief:</p>
        <h3 style="color: #0056b3;">{playbook_title}</h3>
        <hr style="border: none; border-top: 1px solid #eee;" />
        <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #333;">{playbook_content}</pre>
        <hr style="border: none; border-top: 1px solid #eee;" />
        <p style="font-size: 12px; color: #888;">Fulfilled automatically by SolveEase IntentForge Engine v3.0.</p>
    </div>
    """
    
    payload = {
        "from": config.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": f"[SolveEase Playbook] {playbook_title}",
        "html": html_body
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                return True, "Email delivered"
            return False, response.text
    except Exception as e:
        return False, str(e)
