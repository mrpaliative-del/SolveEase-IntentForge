
import re
from typing import Any


MEGA_TAXONOMY = {
    "SEO, Schema & Indexing Fix": {
        "patterns": [
            r"\bseo\b", r"\bmeta(?:\s+tags?)?\b",
            r"\bcanonical\b", r"\bschema\b",
            r"\bsitemap\b", r"\bsearch console\b",
            r"\bbroken links?\b", r"\bredirect(?:s|ion)?\b",
            r"\branking\b", r"\bbacklinks?\b",
            r"\bindex(?:ing|ed)?\b", r"\bcrawl(?:ing|er)?\b",
            r"\brobots?\.txt\b", r"\bstructured data\b",
            r"\bcore web vitals\b", r"\bpage speed\b",
        ],
        "price_cents": 100,
        "priority": 2,
    },
    "E-commerce SKU, Cart & Checkout": {
        "patterns": [
            r"\bshopify\b", r"\bwoocommerce\b",
            r"\bsku\b", r"\binventory\b",
            r"\bproduct feeds?\b", r"\bcart\b",
            r"\bcheckout\b", r"\bstripe\b",
            r"\bpayment(?:s)?\b", r"\border(?:s)?\b",
            r"\bfulfillment\b", r"\bmagento\b",
            r"\bpayment gateway\b", r"\bcart abandonment\b",
            r"\bshipping rates?\b", r"\btax calculation\b",
        ],
        "price_cents": 200,
        "priority": 3,
    },
    "Affiliate Tracking & Webhooks": {
        "patterns": [
            r"\baffiliate(?:s)?\b", r"\bclickbank\b",
            r"\bcommissions?\b", r"\breferrals?\b",
            r"\bpayouts?\b", r"\btracking\b",
            r"\bpixels?\b", r"\bpostbacks?\b",
            r"\bconversions?\b", r"\bsubids?\b",
            r"\brevshare\b", r"\bwebhooks?\b",
            r"\baffiliate links?\b", r"\bcookie duration\b",
            r"\battribution\b", r"\bevent listeners?\b",
        ],
        "price_cents": 300,
        "priority": 4,
    },
    "Google Merchant & Ad Feeds": {
        "patterns": [
            r"\bmerchant center\b", r"\bgtin\b",
            r"\bgoogle ads\b", r"\broas\b",
            r"\bshopping ads?\b", r"\bdisapproved\b",
            r"\bsuspended\b", r"\bsuspension\b",
            r"\bmerchant account\b", r"\bfeed attributes?\b",
            r"\bproduct schema\b", r"\bpolicy violation\b",
            r"\bproduct feed errors?\b",
            r"\bmisrepresentation\b",
        ],
        "price_cents": 500,
        "priority": 5,
    },
    "Technical Bug & Script Fix": {
        "patterns": [
            r"\berrors?\b", r"\bbugs?\b",
            r"\bfix(?:es|ing)?\b", r"\bfail(?:s|ed|ure|ing)?\b",
            r"\bcrashes?\b", r"\bexceptions?\b",
            r"\btracebacks?\b", r"\bimports?\b",
            r"\bsyntax\b", r"\bapi\b",
            r"\bendpoint\b", r"\bjson\b",
            r"\bcsv\b", r"\bspreadsheet\b",
            r"\bnullpointer\b", r"\bundefined\b",
            r"\bstatus(?: code)? 500\b",
            r"\bstatus(?: code)? 400\b",
            r"\brate[- ]limit(?:ing)?\b",
            r"\bshared memory\b", r"\bdocker\b",
        ],
        "price_cents": 100,
        "priority": 1,
    },
}


# Signals that suggest an actual obstacle rather than general discussion.
ACTION_PATTERNS = [
    r"\bnot working\b",
    r"\bdoesn't work\b",
    r"\bdoes not work\b",
    r"\bbroken\b",
    r"\bblocked\b",
    r"\bfailed\b",
    r"\bfailing\b",
    r"\bcan't\b",
    r"\bcannot\b",
    r"\bunable to\b",
    r"\bkeeps? (?:crashing|failing|redirecting)\b",
    r"\bgetting (?:an? )?(?:error|exception)\b",
    r"\bhow do i fix\b",
    r"\bneed help\b",
    r"\bproduction issue\b",
]

ACTION_RE = [re.compile(p, re.IGNORECASE) for p in ACTION_PATTERNS]

COMPILED_TAXONOMY = {
    category: {
        **config,
        "_compiled": [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config["patterns"]
        ],
    }
    for category, config in MEGA_TAXONOMY.items()
}


def classify_signal(text: str) -> dict[str, Any]:
    """
    Classify a public signal using keyword matches and actionability.

    Price is a suggested starting price, not proof of buyer willingness.
    """
    if not isinstance(text, str) or not text.strip():
        return {
            "category": None,
            "price_cents": None,
            "confidence": 0.0,
            "actionable": False,
            "matched_terms": [],
            "status": "rejected_empty",
        }

    normalized = text[:50000]
    matches = []

    for category, config in COMPILED_TAXONOMY.items():
        terms = [
            pattern.pattern
            for pattern in config["_compiled"]
            if pattern.search(normalized)
        ]

        if terms:
            # Distinct matched patterns contribute to the score.
            score = len(terms) + (
                config["priority"] * 0.15
            )

            matches.append({
                "category": category,
                "score": score,
                "price_cents": config["price_cents"],
                "matched_terms": terms,
                "priority": config["priority"],
            })

    if not matches:
        return {
            "category": None,
            "price_cents": None,
            "confidence": 0.0,
            "actionable": False,
            "matched_terms": [],
            "status": "unclassified",
        }

    # Prefer the strongest category match; priority breaks ties.
    matches.sort(
        key=lambda item: (item["score"], item["priority"]),
        reverse=True,
    )

    winner = matches[0]
    total_score = sum(item["score"] for item in matches)
    confidence = winner["score"] / total_score

    actionable = any(
        pattern.search(normalized)
        for pattern in ACTION_RE
    )

    return {
        "category": winner["category"],
        "price_cents": winner["price_cents"],
        "confidence": round(confidence, 3),
        "actionable": actionable,
        "matched_terms": winner["matched_terms"],
        "status": (
            "candidate"
            if actionable and confidence >= 0.50
            else "review_required"
        ),
        "alternative_categories": [
            item["category"] for item in matches[1:3]
        ],
    }
