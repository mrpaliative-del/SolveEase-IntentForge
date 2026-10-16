
import re
from typing import Any


EXCLUSION_PATTERNS = [
    r"\bintroduces\b",
    r"\blaunches a video\b",
    r"\bexplains how\b",
    r"\bwhy seo isn't\b",
    r"\banalysis\s*:",
    r"\btest like a scientist\b",
    r"\bchance of a\b",
    r"\bplugin makes sites\b",
    r"\bshowing advertisers how\b",
    r"\bguide\b",
    r"\boverview\b",
]

# Signals that more directly indicate an obstacle.
PROBLEM_PATTERNS = [
    r"\berrors?\b",
    r"\bbugs?\b",
    r"\bcrash(?:es|ed|ing)?\b",
    r"\bexceptions?\b",
    r"\bfail(?:s|ed|ing|ure)?\b",
    r"\bbroken\b",
    r"\bmissing\b",
    r"\bunauthori[sz]ed\b",
    r"\btimeout\b",
    r"\btime(?:d)? out\b",
    r"\brate[- ]limit(?:ed|ing)?\b",
    r"\bsuspend(?:ed|s|ing)?\b",
    r"\bsuspension\b",
    r"\bwarning\b",
    r"\bnot working\b",
    r"\bdoesn't work\b",
    r"\bdoes not work\b",
    r"\bcan't\b",
    r"\bcannot\b",
    r"\bunable to\b",
    r"\bkeeps? failing\b",
    r"\bkeeps? crashing\b",
    r"\bkeeps? timing out\b",
    r"\bwebhook delivery failed\b",
    r"\binvalid signature\b",
    r"\bpostback(?:s)? not firing\b",
    r"\bcart abandonment due to\b",
    r"\bcheckout (?:fails?|broken|blocked)\b",
    r"\bschema validation failed\b",
    r"\bredirect loop\b",
    r"\bshared memory (?:error|issue|failure)\b",
    r"\bsecurity vulnerability\b",
    r"\bvulnerable\b",
    r"\bdeturpação\b",
]

COMPILED_EXCLUSIONS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in EXCLUSION_PATTERNS
]

COMPILED_PROBLEMS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in PROBLEM_PATTERNS
]


def evaluate_actionable_intent(signal_text: str) -> dict[str, Any]:
    """
    Evaluate whether a signal appears to describe an actionable problem.

    This is a heuristic filter, not proof of buyer intent.
    """
    if not isinstance(signal_text, str) or not signal_text.strip():
        return {
            "actionable": False,
            "status": "rejected_empty",
            "matched_problems": [],
            "matched_exclusions": [],
        }

    text = signal_text[:50000]

    problems = [
        pattern.pattern
        for pattern in COMPILED_PROBLEMS
        if pattern.search(text)
    ]

    exclusions = [
        pattern.pattern
        for pattern in COMPILED_EXCLUSIONS
        if pattern.search(text)
    ]

    # Excluded educational/editorial content can pass only if
    # it also contains a specific problem indicator.
    if exclusions and not problems:
        return {
            "actionable": False,
            "status": "excluded_informational",
            "matched_problems": [],
            "matched_exclusions": exclusions,
        }

    if not problems:
        return {
            "actionable": False,
            "status": "no_problem_evidence",
            "matched_problems": [],
            "matched_exclusions": exclusions,
        }

    return {
        "actionable": True,
        "status": (
            "candidate_needs_review"
            if exclusions
            else "candidate"
        ),
        "matched_problems": problems,
        "matched_exclusions": exclusions,
    }


def is_actionable_intent(signal_text: str) -> bool:
    """Boolean-compatible interface for the ingestion pipeline."""
    result = evaluate_actionable_intent(signal_text)
    return result["actionable"]
