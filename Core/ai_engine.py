"""
AI engine – Cohere-powered fact-checking with source confirmation,
domain-aware prompting and local NLP fallback.
"""
import json
import urllib.request
import urllib.error
import datetime
import logging
import re

from config import config
from .rag_engine import get_live_context
from .nlp_engine import local_analyze

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain / source lists
# ---------------------------------------------------------------------------
SPORTS_KEYWORDS = [
    "cricket", "match", "game", "score", "won", "lost", "defeated", "beat",
    "ipl", "world cup", "t20", "test", "odi", "tournament", "championship",
    "football", "baseball", "basketball", "tennis", "hockey", "rugby",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def extract_key_claims(text: str) -> dict:
    """Extract proper nouns, dates, numbers and outcome verbs from text."""
    return {
        "names": re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text),
        "dates": re.findall(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
            r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
            r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"\s+\d{1,2},?\s+\d{4}\b",
            text,
            re.I,
        ),
        "numbers": re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", text),
        "key_phrases": re.findall(
            r"\b(won|lost|defeated|beat|announced|released|confirmed|"
            r"achieved|reached|signed|launched)\b",
            text,
            re.I,
        ),
    }


def check_source_confirmation(live_context: str, claims: dict, text: str):
    """
    Compare extracted claims against live search results.
    Returns (status, score) where status ∈ {'confirmed','contradicted','silent'}.
    """
    ctx = live_context.lower()
    confirm_score = 0
    contradict_score = 0

    for name in claims["names"][:3]:
        if name.lower() in ctx:
            confirm_score += 2

    for verb in claims["key_phrases"]:
        if verb.lower() in ctx:
            confirm_score += 3

    for date in claims["dates"][:2]:
        if date.lower() in ctx:
            confirm_score += 1

    negation_patterns = [
        r"(?:denied|refuted|debunked|false|incorrect|wrong)",
        r"no evidence",
        r"not found",
        r"no confirmation",
    ]
    for pat in negation_patterns:
        if re.search(pat, ctx):
            contradict_score += 2

    if confirm_score >= 5:
        return "confirmed", confirm_score
    if contradict_score >= 3:
        return "contradicted", contradict_score
    return "silent", 0


def detect_claim_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in SPORTS_KEYWORDS):
        return "sports"
    if re.search(r"\b(?:cure|treatment|disease|virus|vaccine|health)\b", t):
        return "health"
    if re.search(
        r"\b(?:election|government|president|minister|parliament|politician)\b", t
    ):
        return "political"
    return "general"


# ---------------------------------------------------------------------------
# Domain-specific prompt fragments
# ---------------------------------------------------------------------------
_DOMAIN_INSTRUCTIONS = {
    "sports": """
SPORTS CLAIMS RULES:
- Credible sports outlets (ESPN, BBC Sport, NDTV, Times of India Sports) are reliable.
- Match results from reputable sources = confirmed facts.
- Player names + match details + score = high credibility.
- Do NOT require an "official announcement" – sports reporting IS authoritative.
""",
    "health": """
HEALTH CLAIMS RULES:
- Require medical/scientific sources (WHO, CDC, medical journals, hospitals).
- Be VERY sceptical of "miracle cures" or unverified treatments.
- Personal testimonials alone = NOT confirmed.
""",
    "political": """
POLITICAL CLAIMS RULES:
- Major outlets (Reuters, AP, BBC, Guardian) are reliable sources.
- Government official statements = confirmed.
- Election results from election commission / official sources = confirmed.
""",
    "general": """
GENERAL CLAIMS RULES:
- Credible outlets (Reuters, AP, BBC, CNN) = reliable.
- Named organisations + specific details = higher credibility.
- Balance caution with practicality.
""",
}


# ---------------------------------------------------------------------------
# Main AI analysis function
# ---------------------------------------------------------------------------
def ai_analyze(text: str, retry_count: int = 0, max_retries: int = 2):
    """
    Call Cohere and return a parsed result dict, or None on failure.
    """
    if not config.COHERE_API_KEY or config.COHERE_API_KEY.startswith("YOUR_"):
        logger.warning("Cohere API key not configured – skipping AI analysis.")
        return None

    try:
        live_context, source_links = get_live_context(text)
    except Exception as exc:
        logger.error(f"Failed to get live context: {exc}")
        return None

    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    claims = extract_key_claims(text)
    confirmation_status, confirmation_score = check_source_confirmation(
        live_context, claims, text
    )
    claim_type = detect_claim_type(text)
    logger.info(f"Claim type: {claim_type}  |  Source status: {confirmation_status}")

    domain_instruction = _DOMAIN_INSTRUCTIONS[claim_type]

    if confirmation_status == "confirmed":
        source_instruction = (
            f"SOURCE CONFIRMATION: Live sources EXPLICITLY CONFIRM this claim "
            f"(score {confirmation_score}). Strongly supports REAL with 80-95% confidence."
        )
    elif confirmation_status == "contradicted":
        source_instruction = (
            f"SOURCE CONTRADICTION: Live sources CONTRADICT this claim "
            f"(score {confirmation_score}). Strongly supports FAKE with 80-95% confidence."
        )
    else:
        source_instruction = (
            "SOURCE STATUS: Live sources do NOT explicitly mention this claim. "
            "Use credibility signals. Lean REAL (60-75%) if credible signals exist, "
            "else FAKE/UNCERTAIN (50-70%)."
        )

    prompt = f"""You are an expert fact-checker analysing claims against live web search results.

Today's date: {current_date}

CLAIM:
{text}

LIVE SEARCH RESULTS:
{live_context}

{domain_instruction}

{source_instruction}

INSTRUCTIONS:
1. Check if sources confirm or deny the specific claim.
2. Evaluate credibility (specific names, dates, numbers = more credible).
3. Assess language (sensationalism, urgency = red flag; professional tone = good sign).

CONFIDENCE SCORING:
- Sources CONFIRM + Specific Details → 85-95% REAL
- Sources CONTRADICT → 80-95% FAKE
- Sources SILENT + Credible Signals → 65-80% REAL
- Sources SILENT + No Signals → 60-75% FAKE or UNCERTAIN
- Mixed/Ambiguous → 40-60% UNCERTAIN

RED FLAGS (serious issues only):
- Contradicts known facts
- Conspiracy theory language
- Unverifiable health miracle claims
- Sensationalist urgency language

NOT red flags: missing hyperlinks, professional tone, missing details.

Respond ONLY with valid JSON:
{{
  "chain_of_thought": "Brief reasoning",
  "verdict": "FAKE" or "REAL" or "UNCERTAIN",
  "confidence": <0-100>,
  "reason": "<One clear sentence>",
  "fact_check": "<What sources confirm/deny>",
  "red_flags": ["<serious issues only>"],
  "recommendations": ["<action>"]
}}
"""

    payload = json.dumps(
        {
            "model": config.COHERE_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "Analyse this claim based on the search results above.",
                },
            ],
            "temperature": 0.0,
            "max_tokens": 600,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        config.COHERE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.COHERE_API_KEY}",
            "X-Client-Name": "debunkit",
        },
        method="POST",
    )

    try:
        logger.info(f"Calling Cohere API (attempt {retry_count + 1}/{max_retries + 1})…")
        with urllib.request.urlopen(req, timeout=config.COHERE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        raw = data["message"]["content"][0]["text"].strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        result["sources"] = source_links

        # Confidence boost when sources align with verdict
        if confirmation_status == "confirmed" and result.get("verdict") == "REAL":
            result["confidence"] = min(result.get("confidence", 80) + 10, 95)
        if confirmation_status == "contradicted" and result.get("verdict") == "FAKE":
            result["confidence"] = min(result.get("confidence", 80) + 10, 95)

        logger.info(
            f"Cohere OK: {result.get('verdict')} ({result.get('confidence')}%)"
        )
        return result

    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning(f"Network/timeout error (attempt {retry_count + 1}): {exc}")
        if retry_count < max_retries:
            return ai_analyze(text, retry_count + 1, max_retries)
        logger.error("AI analysis failed – falling back to local NLP.")
        return None

    except urllib.error.HTTPError as exc:
        logger.error(f"HTTP error {exc.code}: {exc.read().decode()}")
        if exc.code == 401:
            logger.error("Auth failed – check Cohere API key.")
            return None
        if retry_count < max_retries:
            return ai_analyze(text, retry_count + 1, max_retries)
        return None

    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Parse error: {exc}")
        return None

    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Hybrid analysis (AI → local NLP fallback)
# ---------------------------------------------------------------------------
def hybrid_analyze(text: str) -> dict:
    """Run AI analysis; fall back to local NLP if unavailable."""
    logger.info("Starting hybrid analysis…")

    ai_result = ai_analyze(text)
    if ai_result:
        logger.info(
            f"AI analysis OK: {ai_result['verdict']} ({ai_result['confidence']}%)"
        )
        return {
            "verdict": ai_result["verdict"],
            "confidence": ai_result["confidence"],
            "reason": ai_result.get("reason", ""),
            "fact_check": ai_result.get("fact_check", ""),
            "red_flags": ai_result.get("red_flags", [])[:6],
            "recommendations": ai_result.get("recommendations", []),
            "sources": ai_result.get("sources", []),
            "mode": "ai",
        }

    logger.info("AI unavailable – using local NLP fallback.")
    local = local_analyze(text)
    net = local["net_score"]
    claim_flags = local["claim_flags"]
    credible_hits = local["credible_hits"]

    if net >= 35 or (claim_flags and credible_hits < 2):
        verdict = "FAKE"
        confidence = min(50 + net // 2, 90)
        reason = claim_flags[0] if claim_flags else "Multiple misinformation patterns detected."
    else:
        verdict = "REAL"
        confidence = min(50 + credible_hits * 6, 85)
        reason = "No major misinformation signals detected."

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "fact_check": "AI analysis unavailable – using local pattern analysis only.",
        "red_flags": local["red_flags"],
        "recommendations": ["Connect to the internet for AI-powered fact-checking."],
        "sources": [],
        "mode": "local_fallback",
    }
