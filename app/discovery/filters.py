import hashlib
from app.discovery.taxonomy import TAXONOMY_PATTERNS

def evaluate_intent(title: str, body: str):
    text = f"{title} {body}".lower()
    
    for pattern in TAXONOMY_PATTERNS:
        for kw in pattern["keywords"]:
            if kw in text:
                raw_hash = f"{pattern['domain']}_{title}".encode('utf-8')
                task_hash = hashlib.sha256(raw_hash).hexdigest()[:16]
                return {
                    "matched": True,
                    "task_hash": task_hash,
                    "domain": pattern["domain"],
                    "price": pattern["base_price"]
                }
                
    return {"matched": False}
