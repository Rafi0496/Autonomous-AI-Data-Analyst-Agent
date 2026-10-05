"""Synthesis Guardrails: Forbidden phrases and causal speculation enforcement (Milestone 3).

Enforces:
- Strict prohibition of forbidden words: 'stable', 'not concentrated', 'no effect', 'organic'.
- Prohibition of causal speculation: 'leads to', 'causes', 'caused by', 'drives', 'driven by', 'resulting in', 'because of'.
- Post-check verification and sanitization.
"""
import re
from typing import List, Tuple
from backend.app.services.insights import validate_no_placeholders

FORBIDDEN_TERMS = [
    (r"\bstable\b", "consistent"),
    (r"\bnot\s+concentrated\b", "distributed across categories"),
    (r"\bno\s+effect\b", "no statistically significant difference detected"),
    (r"\borganic\b", "unadjusted"),
]

CAUSAL_PATTERNS = [
    (r"\bleads\s+to\b", "is associated with"),
    (r"\bcaused\s+by\b", "correlated with"),
    (r"\bcauses\b", "is correlated with"),
    (r"\bdriven\s+by\b", "associated with"),
    (r"\bdrives\b", "is associated with"),
    (r"\bresulting\s+in\b", "accompanied by"),
    (r"\bbecause\s+of\b", "in the presence of"),
]


def check_forbidden_narrative_terms(text: str) -> List[str]:
    """Scan text for forbidden terms and causal speculation phrases."""
    if not text:
        return []
    violations = []
    text_lower = text.lower()
    for pat, _ in FORBIDDEN_TERMS + CAUSAL_PATTERNS:
        if re.search(pat, text_lower):
            violations.append(pat)
    return violations


def post_check_synthesis_narrative(text: str, context: str = "synthesis narrative") -> str:
    """
    Post-check narrative text for forbidden phrases and causal speculation.
    Sanitizes detected phrases, strips sentences if violations cannot be cleanly resolved,
    and asserts zero forbidden terms or placeholders remain.
    """
    if not text or not isinstance(text, str):
        return text

    cleaned = text
    # 1. Apply term sanitization
    for pat, repl in FORBIDDEN_TERMS:
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)

    for pat, repl in CAUSAL_PATTERNS:
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)

    # 2. Check if any forbidden patterns remain; if so, strip offending sentences
    violations = check_forbidden_narrative_terms(cleaned)
    if violations:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        kept = []
        for s in sentences:
            if not check_forbidden_narrative_terms(s):
                kept.append(s)
        cleaned = " ".join(kept)

    # 3. Final validation against placeholders
    cleaned = validate_no_placeholders(cleaned, context)

    # Ensure zero forbidden tokens
    for pat, _ in FORBIDDEN_TERMS:
        if re.search(pat, cleaned, re.IGNORECASE):
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()
