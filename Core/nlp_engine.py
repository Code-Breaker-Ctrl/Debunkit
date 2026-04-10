"""
Local NLP engine – lightweight fallback when AI API is unavailable.
Uses keyword matching and heuristics.
"""
import re
import logging

logger = logging.getLogger(__name__)

# --- Fake-news signal patterns ---
MISINFORMATION_PATTERNS = [
    (r"\bbreaking\b.*!{2,}", 5),
    (r"\bshare before (it'?s? )?deleted\b", 15),
    (r"\bthey don'?t want you to know\b", 15),
    (r"\bwake up\b.*\bsheep\b", 10),
    (r"\bsecret cure\b", 10),
    (r"\bgovernment.*hiding\b", 8),
    (r"\bhoax\b", 5),
    (r"\bconspiracy\b", 5),
    (r"\bmiracl(e|ous)\b", 4),
    (r"\b100\s*%\s*(natural|safe|cure)\b", 6),
    (r"\bclick (here|now)\b", 3),
    (r"!{3,}", 3),
    (r"\bFAKE NEWS\b", 8),
    (r"\bdeep state\b", 8),
]

CREDIBLE_SOURCE_PATTERNS = [
    r"\breuters\b",
    r"\bassociated press\b",
    r"\bap news\b",
    r"\bbbc\b",
    r"\bcnn\b",
    r"\bnew york times\b",
    r"\bguardian\b",
    r"\bwashington post\b",
    r"\bwho\b",
    r"\bcdc\b",
    r"\bnasa\b",
    r"\buniversity\b",
    r"\bjournal\b",
    r"\bofficial\b",
    r"\bgovernment\b",
    r"\bministry\b",
    r"\bespn\b",
    r"\bndtv\b",
    r"\btimes of india\b",
]


def local_analyze(text: str) -> dict:
    """Return a dict with net_score, claim_flags, credible_hits, red_flags."""
    text_lower = text.lower()
    net_score = 0
    claim_flags = []
    red_flags = []

    for pattern, weight in MISINFORMATION_PATTERNS:
        if re.search(pattern, text_lower):
            net_score += weight
            red_flags.append(f"Pattern detected: {pattern}")
            claim_flags.append(f"Suspicious language: {pattern}")

    credible_hits = sum(
        1 for p in CREDIBLE_SOURCE_PATTERNS if re.search(p, text_lower)
    )

    return {
        "net_score": net_score,
        "claim_flags": claim_flags,
        "credible_hits": credible_hits,
        "red_flags": red_flags,
    }
