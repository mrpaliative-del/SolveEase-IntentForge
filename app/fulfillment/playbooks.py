
from datetime import datetime, timezone
from html import escape
from typing import Optional


def generate_tiered_playbook(
    tier: str,
    raw_signal: str,
    *,
    source_url: Optional[str] = None,
    category: Optional[str] = None,
    matched_evidence: Optional[list[str]] = None,
) -> str:
    """
    Generate a report from a public problem signal.

    This creates a structured analysis template, not a verified fix.
    Supply source_url and matched_evidence when available.
    """

    tier_normalized = (tier or "").strip().lower()

    if "brief" in tier_normalized:
        report_tier = "Brief"
        price_label = "$1.00"
    elif "playbook" in tier_normalized or "premium" in tier_normalized:
        report_tier = "Technical Playbook"
        price_label = "$3.00–$5.00"
    else:
        raise ValueError(
            "Unsupported tier. Use 'Brief' or 'Technical Playbook'."
        )

    if not isinstance(raw_signal, str) or not raw_signal.strip():
        raise ValueError("raw_signal must contain problem evidence.")

    # Bound the size of untrusted source material.
    signal = raw_signal.strip()[:5000]
    evidence = matched_evidence or []

    # Escape source text so embedded markup cannot alter report formatting.
    safe_signal = escape(signal)
    safe_category = escape(category or "Unclassified")
    safe_source = escape(source_url or "Source URL not provided")
    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    evidence_section = (
        "\n".join(f"- {escape(item[:500])}" for item in evidence[:10])
        if evidence
        else "- No independently verified diagnostic evidence supplied."
    )

    if report_tier == "Brief":
        return f"""\
# SolveEase Problem Brief

**Tier:** Brief ({price_label})
**Category:** {safe_category}
**Generated:** {generated_at}

## 1. Observed signal

{safe_signal}

## 2. What this evidence establishes

The supplied text indicates a potential problem. It does not, by itself,
confirm the root cause, business impact, or existence of a working fix.

## 3. Initial diagnostic checklist

1. Reproduce the reported behavior, if access to the affected system is available.
2. Record the relevant error message, timestamp, and affected component.
3. Compare expected behavior with actual behavior.
4. Check recent configuration, code, integration, or data changes.
5. Confirm the suspected cause before applying a change.

## 4. Evidence available

{evidence_section}

## 5. Source

{safe_source}

## Limitations

This brief is generated from supplied signal text. No live system inspection,
patch execution, or regression test is claimed.
"""

    return f"""\
# SolveEase Technical Resolution Playbook

**Tier:** Technical Playbook ({price_label})
**Category:** {safe_category}
**Generated:** {generated_at}

## 1. Problem context

{safe_signal}

**Evidence source:** {safe_source}

## 2. Evidence and confidence boundaries

{evidence_section}

Separate reported symptoms from confirmed facts. Do not assume that a
particular endpoint, schema, encoding problem, or timeout is responsible
unless supporting evidence establishes it.

## 3. Reproduction plan

1. Record the expected and actual behavior.
2. Identify the affected component and a minimal reproducible example.
3. Capture relevant logs, response codes, timestamps, and sanitized inputs.
4. Reproduce in a local or staging environment where possible.
5. Document whether the issue is consistent, intermittent, or not reproduced.

## 4. Diagnostic decision path

- **Input or schema problem:** validate required fields, types, and constraints.
- **Integration or authentication problem:** inspect response codes, permissions,
  credentials configuration, and request signatures without exposing secrets.
- **Timeout or rate-limit problem:** inspect latency, retry behavior, provider
  limits, and request volume.
- **Runtime or deployment problem:** inspect sanitized stack traces, dependency
  versions, environment configuration, and recent deployment changes.
- **No matching evidence:** gather additional diagnostics before proposing a patch.

These are diagnostic branches, not claims about the confirmed root cause.

## 5. Proposed resolution

Choose a fix only after the relevant diagnostic branch is supported by evidence.
Document:

- Confirmed root cause
- Proposed code or configuration change
- Expected effect
- Potential regressions and rollback procedure

No patch is represented as tested unless actual test results are attached.

## 6. Verification checklist

- [ ] Reproduce the original issue before the fix.
- [ ] Test the proposed change in a safe environment.
- [ ] Run relevant regression tests.
- [ ] Confirm the original failure no longer occurs.
- [ ] Check related workflows for regressions.
- [ ] Monitor logs and metrics after deployment.
- [ ] Document the result, including any unresolved limitations.

## 7. Completion status

**Status:** Diagnostic playbook generated; fix and verification not confirmed.

## Scope and limitations

This report is based on the supplied signal and available evidence.
It does not imply access to the affected system, execution of a patch,
or confirmation that the problem has been resolved.
"""
