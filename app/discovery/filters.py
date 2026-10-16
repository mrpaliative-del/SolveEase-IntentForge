
import re
from typing import Any


# Strong evidence that a real obstacle or missing capability exists.
PROBLEM_PATTERNS = [
    r"\berrors?\b",
    r"\bbugs?\b",
    r"\bcrash(?:es|ed|ing)?\b",
    r"\bexceptions?\b",
    r"\bfail(?:s|ed|ing|ure|ures)?\b",
    r"\bbroken\b",
    r"\bmissing\b",
    r"\blacks?\b",
    r"\bdoes not support\b",
    r"\bdoesn't support\b",
    r"\bnot supported\b",
    r"\bnot working\b",
    r"\bdoesn't work\b",
    r"\bdoes not work\b",
    r"\bcan't\b",
    r"\bcannot\b",
    r"\bunable to\b",
    r"\bunauthori[sz]ed\b",
    r"\btimeout\b",
    r"\btimed out\b",
    r"\brate[- ]limit(?:ed|ing)?\b",
    r"\bsuspend(?:ed|s|ing)?\b",
    r"\bsuspension\b",
    r"\bwebhook delivery failed\b",
    r"\bwebhook(?:s)? (?:not firing|not delivered|failing)\b",
    r"\binvalid signature\b",
    r"\bpostback(?:s)? not firing\b",
    r"\bcheckout (?:fails?|broken|blocked)\b",
    r"\bschema validation failed\b",
    r"\bredirect loop\b",
    r"\bsecurity vulnerability\b",
    r"\bvulnerable\b",
    r"\bnot indexing\b",
    r"\bde[- ]?indexed\b",
    r"\bdisapproved\b",
    r"\bkeeps? (?:failing|crashing|timing out)\b",
    r"\bwon't load\b",
    r"\bwill not load\b",
    r"\bproduction issue\b",
    r"\bdoes not exist\b",
    r"\bnot receiving\b",
    r"\bincorrect(?:ly)?\b",
]

# Evidence that the author is describing their own issue,
# requesting assistance, or reporting a reproducible defect.
INTENT_PATTERNS = [
    r"\bi (?:am|'m) (?:getting|seeing|experiencing|facing)\b",
    r"\bi (?:tried|attempted) .{0,100}\b(?:but|and)\b",
    r"\bi need help\b",
    r"\bneed help (?:fixing|with|resolving)\b",
    r"\bhow (?:can|do) i fix\b",
    r"\bhow can i resolve\b",
    r"\banyone know how to fix\b",
    r"\bcan someone help\b",
    r"\bwhat am i doing wrong\b",
    r"\bsteps to reproduce\b",
    r"\bexpected (?:behavior|result)\b",
    r"\bactual (?:behavior|result)\b",
    r"\bcurrent behavior\b",
    r"\bunable to\b",
    r"\bnot working\b",
    r"\bdoesn't work\b",
    r"\bdoes not work\b",
    r"\bkeeps? (?:failing|crashing|timing out)\b",
    r"\bwebhook delivery failed\b",
    r"\bcheckout (?:fails?|broken|blocked)\b",
    r"\bmissing (?:feature|functionality|support|option|endpoint)\b",
    r"\blacks? (?:support|a way|an option|functionality|the ability)\b",
    r"\bdoes not support\b",
    r"\bdoesn't support\b",
    r"\bnot supported\b",
]

# Reject obvious announcements and editorial content unless
# there is also clear help-seeking or defect-report evidence.
EDITORIAL_PATTERNS = [
    r"\bi (?:built|created|launched|released|made) .{0,100}\b(?:tool|engine|plugin|product|project|app)\b",
    r"\bintroducing\b",
    r"\blaunch(?:es|ed)?\b",
    r"\bchangelog\b",
    r"\brelease notes\b",
    r"\bproduction operations status\b",
    r"\bparser health\b",
    r"\bbeginner'?s guide\b",
    r"\bultimate guide\b",
    r"\btips and tricks\b",
    r"\bwhat is\b",
    r"\beverything you need to know\b",
    r"\bcomparison\b",
    r"\boverview\b",
    r"\btutorial\b",
    r"\bhow-to guide\b",
]

COMPILED_PROBLEMS = [
    re.compile(p, re.IGNORECASE) for p in PROBLEM_PATTERNS
]
COMPILED_INTENTS = [
    re.compile(p, re.IGNORECASE) for p in INTENT_PATTERNS
]
COMPILED_EDITORIAL = [
    re.compile(p, re.IGNORECASE) for p in EDITORIAL_PATTERNS
]


def evaluate_actionable_intent(signal_text: str) -> dict[str, Any]:
    """Heuristic triage only; it cannot prove demand or willingness to pay."""
    if not isinstance(signal_text, str) or not signal_text.strip():
        return {
            "actionable": False,
            "status": "rejected_empty",
            "matched_problems": [],
            "matched_intents": [],
            "matched_exclusions": [],
        }

    text = re.sub(r"\s+", " ", signal_text[:50000]).strip()

    problems = [p.pattern for p in COMPILED_PROBLEMS if p.search(text)]
    intents = [p.pattern for p in COMPILED_INTENTS if p.search(text)]
    exclusions = [p.pattern for p in COMPILED_EDITORIAL if p.search(text)]

    if not problems:
        status = "no_problem_evidence"
        actionable = False
    elif exclusions and not intents:
        status = "excluded_announcement_or_editorial"
        actionable = False
    elif not intents:
        status = "review_required"
        actionable = False
    else:
        status = "candidate_needs_review"
        actionable = True

    return {
        "actionable": actionable,
        "status": status,
        "matched_problems": problems,
        "matched_intents": intents,
        "matched_exclusions": exclusions,
    }


def is_actionable_intent(signal_text: str) -> bool:
    """Backward-compatible interface for the existing ingestion pipeline."""
    return evaluate_actionable_intent(signal_text)["actionable"]
