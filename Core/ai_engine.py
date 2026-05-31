import json
import urllib.request
import urllib.error
import datetime
import logging
import re
from urllib.parse import urlparse

from config import config
from .rag_engine import get_live_context
from .nlp_engine import local_analyze

logger = logging.getLogger(__name__)


VALID_VERDICTS = {
    "SUPPORTED",
    "REFUTED",
    "INSUFFICIENT EVIDENCE",
    "MISLEADING",
    "LOW CREDIBILITY"
}

VERDICT_ALIASES = {
    "REAL": "SUPPORTED",
    "TRUE": "SUPPORTED",
    "CONFIRMED": "SUPPORTED",
    "FAKE": "REFUTED",
    "FALSE": "REFUTED",
    "DEBUNKED": "REFUTED",
    "UNCERTAIN": "INSUFFICIENT EVIDENCE",
    "UNKNOWN": "INSUFFICIENT EVIDENCE",
    "UNVERIFIED": "INSUFFICIENT EVIDENCE",
    "SUSPICIOUS": "LOW CREDIBILITY"
}


# ===== CREDIBLE SOURCE SIGNALS =====

CREDIBLE_NEWS_SOURCES = [
    "reuters", "associated press", "ap news", "bbc", "cnn", "nyt", "times",
    "guardian", "washington post", "fox news", "nbcnews", "abcnews",
    "espn", "bbc sport", "ndtv", "times of india", "hindu", "deccan",
    "scroll", "theprint", "news18", "india today", "aaj tak",
    "the hindu", "hindustan times", "indian express", "cricbuzz",
    "espncricinfo"
]

CREDIBLE_SOURCE_DOMAINS = [
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "thehindu.com",
    "hindustantimes.com",
    "indianexpress.com",
    "indiatoday.in",
    "ndtv.com",
    "timesofindia.indiatimes.com",
    "news18.com",
    "theprint.in",
    "scroll.in",
    "deccanherald.com",
    "espncricinfo.com",
    "espn.com",
    "cricbuzz.com"
]

CREDIBLE_INSTITUTIONS = [
    "stanford", "harvard", "mit", "yale", "berkeley", "oxford", "cambridge",
    "google", "microsoft", "apple", "nasa", "fed", "world bank", "un",
    "iit", "delhi university", "mumbai university"
]

SPORTS_KEYWORDS = [
    "cricket", "match", "game", "score", "won", "lost", "defeated", "beat",
    "ipl", "world cup", "t20", "test", "odi", "tournament", "championship",
    "football", "baseball", "basketball", "tennis", "hockey", "rugby",
    "player", "coach", "fielding", "batting", "bowling"
]

HIGH_RISK_TERMS = [
    "death", "dead", "died", "murder", "arrest", "arrested", "jailed",
    "resigned", "resignation", "election", "minister", "president",
    "prime minister", "stock", "share price", "bankruptcy", "fraud",
    "war", "attack", "terror", "disease", "virus", "vaccine", "cure",
    "medicine", "treatment", "miracle cure", "hantavirus"
]


# ===== BASIC NORMALIZATION =====

def normalize_verdict(verdict):
    """
    Convert old/simple model labels into professional fact-check labels.
    """
    if not verdict:
        return "INSUFFICIENT EVIDENCE"

    verdict = str(verdict).strip().upper()
    verdict = VERDICT_ALIASES.get(verdict, verdict)

    if verdict not in VALID_VERDICTS:
        logger.warning(
            f"Unexpected verdict received: {verdict}. "
            "Defaulting to INSUFFICIENT EVIDENCE."
        )
        return "INSUFFICIENT EVIDENCE"

    return verdict


def clamp_confidence(value, default=50):
    """
    Keep confidence inside a safe 0-100 integer range.
    """
    try:
        value = int(float(value))
    except (TypeError, ValueError):
        return default

    return max(0, min(value, 100))


def extract_domain(url):
    """
    Extract hostname from a URL.
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower()
    except Exception:
        return ""


def is_credible_source_url(url):
    """
    Check whether a submitted URL belongs to a known credible source domain.
    """
    domain = extract_domain(url)

    if not domain:
        return False

    for trusted_domain in CREDIBLE_SOURCE_DOMAINS:
        if domain == trusted_domain or domain.endswith("." + trusted_domain):
            return True

    return False


def is_credible_source_block(block):
    """
    Quick credibility check based on source names/domains.
    """
    block = block.lower()
    trusted_terms = CREDIBLE_NEWS_SOURCES + CREDIBLE_INSTITUTIONS + CREDIBLE_SOURCE_DOMAINS
    return any(term in block for term in trusted_terms)


def has_high_risk_terms(text):
    """
    High-risk claims need stronger verification and should not be auto-supported
    just because one article/source exists.
    """
    text_lower = text.lower()
    return any(term in text_lower for term in HIGH_RISK_TERMS)


def has_causal_claim(text):
    """
    Claims with cause/reason wording need exact support for the reason,
    not just same-topic support.
    """
    text_lower = text.lower()

    causal_patterns = [
        "because",
        "due to",
        "as a result of",
        "caused by",
        "dropped because",
        "removed because",
        "fired because",
        "banned because",
        "rejected because"
    ]

    return any(pattern in text_lower for pattern in causal_patterns)


def merge_sources(submitted_url, source_links):
    """
    Add submitted URL as a source, then merge live-search sources without duplicates.
    """
    merged = []
    seen = set()

    if submitted_url:
        merged.append({
            "title": "Submitted article",
            "url": submitted_url
        })
        seen.add(submitted_url)

    for src in source_links or []:
        url = src.get("url")
        title = src.get("title", "Source")

        if not url or url in seen:
            continue

        merged.append({
            "title": title,
            "url": url
        })
        seen.add(url)

    return merged[:8]


# ===== CLAIM EXTRACTION =====

def extract_key_claims(text):
    """
    Extract main claim signals/entities from text for source matching.
    """
    claims = {
        "names": re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text),
        "dates": re.findall(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}?,?\s+\d{4}\b",
            text,
            re.I
        ),
        "years": re.findall(r"\b20\d{2}\b", text),
        "numbers": re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", text),
        "key_phrases": []
    }

    action_terms = re.findall(
        r"\b("
        r"won|lost|defeated|beat|announced|released|confirmed|achieved|reached|"
        r"resigned|died|dead|arrested|jailed|fired|removed|appointed|selected|"
        r"elected|banned|launched|introduced|approved|rejected|cancelled|canceled|"
        r"keynote|speaker|deliver|delivered|claims|said|reports|reported|"
        r"swats|doubts|backs|supports|criticises|criticizes|questions|"
        r"dropped|removed|misrepresented|miscaptioned|predicted|warned"
        r")\b",
        text,
        re.I
    )

    claims["key_phrases"] = list(dict.fromkeys([term.lower() for term in action_terms]))
    return claims


def _extract_source_blocks(live_context):
    """
    Extract individual source blocks from the context string.
    """
    pattern = re.compile(
        r"\n\d+\.\s\[(.*?)\]\n\s*URL:\s*(.*?)\n\s*Snippet:\s*(.*?)(?=\n\d+\.|\Z)",
        re.S | re.I
    )

    blocks = []

    for match in pattern.finditer(live_context):
        blocks.append(match.group(0).lower())

    return blocks


def check_source_confirmation(live_context, claims, text):
    """
    Conservative source check.

    Returns:
        ("supported", score)
        ("refuted", score)
        ("insufficient", score)
    """
    source_blocks = _extract_source_blocks(live_context)

    if not source_blocks:
        return "insufficient", 0

    matched_sources = 0
    refuting_sources = 0
    evidence_score = 0

    names = [name.lower() for name in claims.get("names", [])[:3]]
    phrases = [phrase.lower() for phrase in claims.get("key_phrases", [])]
    dates = [date.lower() for date in claims.get("dates", [])[:2]]
    years = claims.get("years", [])[:2]
    numbers = claims.get("numbers", [])[:2]

    refutation_patterns = [
        r"\bdenied\b",
        r"\brefuted\b",
        r"\bdebunked\b",
        r"\bfalse\b",
        r"\bincorrect\b",
        r"\bwrong\b",
        r"\bno evidence\b",
        r"\bnot true\b",
        r"\bdid not\b",
        r"\bdoes not\b",
        r"\bhas not\b",
        r"\bno confirmation\b",
        r"\bmisleading\b",
        r"\bmisrepresented\b",
        r"\bmiscaptioned\b",
        r"\bold video\b",
        r"\bold footage\b"
    ]

    for block in source_blocks:
        has_name = any(name in block for name in names) if names else False
        has_phrase = any(phrase in block for phrase in phrases) if phrases else False
        has_date = any(date in block for date in dates) if dates else False
        has_year = any(year in block for year in years) if years else False
        has_number = any(num in block for num in numbers) if numbers else False
        is_credible = is_credible_source_block(block)

        detail_hits = sum([has_date, has_year, has_number])
        refutes = any(re.search(pattern, block) for pattern in refutation_patterns)

        if refutes and (has_name or has_phrase or detail_hits):
            refuting_sources += 1
            evidence_score += 4

            if is_credible:
                evidence_score += 1

            continue

        if has_name and has_phrase:
            matched_sources += 1
            evidence_score += 3

            if detail_hits:
                evidence_score += 1

            if is_credible:
                evidence_score += 1

    total_sources = len(source_blocks)

    if refuting_sources >= 1:
        return "refuted", evidence_score

    if matched_sources >= 2:
        return "supported", evidence_score

    if matched_sources == 1 and evidence_score >= 5 and total_sources <= 2:
        return "supported", evidence_score

    return "insufficient", evidence_score


def detect_factcheck_override(live_context, claim_text):
    """
    Detect when a fact-check source clearly corrects, refutes, or adds missing context.

    This stops the AI from marking a claim SUPPORTED just because
    normal news results mention the same topic.
    """
    source_blocks = _extract_source_blocks(live_context)

    if not source_blocks:
        return None

    claim_lower = claim_text.lower()

    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "were", "was",
        "are", "has", "have", "inside", "shows", "showing", "held", "about",
        "over", "into", "their", "there", "where", "when", "what", "will",
        "would", "could", "should"
    }

    claim_terms = [
        word.lower()
        for word in re.findall(r"\b[a-zA-Z]{4,}\b", claim_lower)
        if word.lower() not in stop_words
    ]

    factcheck_markers = [
        "fact check",
        "fact-check",
        "reuters.com/fact-check",
        "snopes",
        "politifact",
        "full fact",
        "afp fact check",
        "boomlive",
        "alt news",
        "logically facts"
    ]

    misleading_markers = [
        "misleading",
        "missing context",
        "miscaptioned",
        "misrepresented",
        "old video",
        "old footage",
        "old image",
        "not from",
        "not the",
        "shared as",
        "captioned as",
        "different route",
        "different routes",
        "not in the uk",
        "not in uk",
        "taken out of context"
    ]

    refuting_markers = [
        "false",
        "did not",
        "does not",
        "not true",
        "no evidence",
        "fabricated",
        "fake",
        "altered",
        "ai-generated",
        "contrary to",
        "no record",
        "didn't",
        "doesn't"
    ]

    for block in source_blocks:
        is_factcheck = any(marker in block for marker in factcheck_markers)

        if not is_factcheck:
            continue

        overlap = sum(1 for term in claim_terms if term in block)

        # Need overlap so unrelated fact-check pages do not override.
        if overlap < 2:
            continue

        has_misleading_signal = any(marker in block for marker in misleading_markers)
        has_refuting_signal = any(marker in block for marker in refuting_markers)

        if has_refuting_signal:
            return {
                "verdict": "REFUTED",
                "confidence": 85,
                "reason": "A fact-check source directly contradicts the central claim.",
                "fact_check": (
                    "A fact-check result in the live search context contains refuting language "
                    "such as 'did not', 'false', 'no evidence', or similar wording."
                ),
                "red_flags": ["Fact-check source contradicts the claim"]
            }

        if has_misleading_signal:
            return {
                "verdict": "MISLEADING",
                "confidence": 82,
                "reason": "A fact-check source says the claim is missing context or misrepresents the situation.",
                "fact_check": (
                    "A fact-check result in the live search context indicates that the claim uses "
                    "old, miscaptioned, misrepresented, or incomplete context."
                ),
                "red_flags": ["Fact-check source reports missing context"]
            }

    return None


def detect_claim_type(text):
    """
    Detect the type of claim.
    """
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in SPORTS_KEYWORDS):
        return "sports"

    if re.search(r"\b(?:cure|treatment|disease|virus|vaccine|health|medicine|hantavirus)\b", text_lower):
        return "health"

    if re.search(r"\b(?:election|government|president|minister|parliament|politician)\b", text_lower):
        return "political"

    return "general"


# ===== AI ANALYSIS =====

def ai_analyze(
    text,
    input_type="text",
    source_url=None,
    source_text=None,
    retry_count=0,
    max_retries=2
):
    """
    Analyze text using Cohere AI API with source-aware evaluation.
    URL mode is treated differently from raw text/headline mode.
    """
    if not config.COHERE_API_KEY or config.COHERE_API_KEY.startswith("YOUR_"):
        logger.warning("Cohere API key not configured. Skipping AI analysis.")
        return None

    try:
        logger.info("Fetching live context from web search...")
        live_context, source_links = get_live_context(text)
    except Exception as e:
        logger.error(f"Failed to get live context: {e}")
        return None

    current_date = datetime.datetime.now().strftime("%B %d, %Y")

    claims = extract_key_claims(text)
    confirmation_status, confirmation_score = check_source_confirmation(live_context, claims, text)
    factcheck_override = detect_factcheck_override(live_context, text)
    claim_type = detect_claim_type(text)

    submitted_url_is_credible = is_credible_source_url(source_url)
    high_risk_claim = has_high_risk_terms(text)
    causal_claim = has_causal_claim(text)

    logger.info(
        f"Claim type: {claim_type}, Source status: {confirmation_status}, "
        f"URL mode: {input_type == 'url'}, Credible URL: {submitted_url_is_credible}, "
        f"High risk: {high_risk_claim}, Causal claim: {causal_claim}"
    )

    # Domain-specific prompt instructions
    if claim_type == "sports":
        domain_instruction = """
SPORTS CLAIMS RULES:
- Credible sports news outlets and established newspapers are reliable for routine sports reporting.
- Match reports, player statements, coach statements, and article-based sports updates can be treated as routine news.
- Do not require an official government-style announcement for normal sports reporting.
- Player names + team/league context + professional article = meaningful evidence.
- But causal claims like "dropped because he is poor" need direct evidence for that exact reason.
"""
    elif claim_type == "health":
        domain_instruction = """
HEALTH CLAIMS RULES:
- Require medical/scientific sources such as WHO, CDC, government health bodies, hospitals, or peer-reviewed research.
- Be very skeptical of miracle cures or unverified treatments.
- A news article alone is not enough to mark health claims as supported.
- If fact-check sources say the claim is misleading or false, prioritize those fact-checks.
"""
    elif claim_type == "political":
        domain_instruction = """
POLITICAL CLAIMS RULES:
- Reuters, AP, BBC, major newspapers, and official government statements are reliable.
- For election results, laws, resignations, arrests, and public-office claims, require stronger evidence.
- Avoid marking political claims as supported if only weak snippets are available.
"""
    else:
        domain_instruction = """
GENERAL CLAIMS RULES:
- Credible news sources are reliable for routine factual reporting.
- Named organizations, dates, and specific details increase credibility.
- Extraordinary claims require stronger evidence.
- Video/photo claims need extra caution because old or unrelated media is often recaptioned.
"""

    # URL-aware instruction
    if input_type == "url" and source_url:
        url_instruction = f"""
SUBMITTED URL MODE:
- The user submitted a URL, and the webpage was successfully scraped.
- Submitted URL: {source_url}
- Recognized credible source domain: {submitted_url_is_credible}
- High-risk claim category detected: {high_risk_claim}

How to use the submitted article:
- Treat the submitted article text as PRIMARY EVIDENCE of what that source reports.
- If the submitted article is from a recognized credible source and the claim is routine sports/general news, you may choose SUPPORTED with moderate confidence even if live-search snippets do not repeat the exact headline.
- If the submitted article is from an unknown/weak source, do NOT mark SUPPORTED based only on the article itself.
- If the claim is high-risk, medical, death, arrest, election, finance, or public-safety related, require stronger external corroboration.
- If external sources clearly contradict the submitted article, choose REFUTED or MISLEADING.
- Do not mark INSUFFICIENT EVIDENCE only because the live snippets are incomplete when the submitted source itself is credible and directly reports the routine claim.
"""
    else:
        url_instruction = """
TEXT/HEADLINE MODE:
- The user submitted plain text or a headline, not a source article.
- Do not assume the claim is true without external support.
- Use live web results as the main evidence.
- Same-topic search results are not enough; the central subject and central event/reason must match.
"""

    # Source confirmation instruction
    if confirmation_status == "supported":
        source_instruction = f"""
SOURCE STATUS:
Preliminary source matching found possible supporting evidence with score {confirmation_score}.
You may choose SUPPORTED if the central subject and action/event match the sources.
If the claim includes a specific cause/reason, that cause/reason must also be supported.
"""
    elif confirmation_status == "refuted":
        source_instruction = f"""
SOURCE STATUS:
Preliminary source matching found possible refuting or corrective evidence with score {confirmation_score}.
If credible sources deny, correct, contradict, or add missing context to the central claim, choose REFUTED or MISLEADING.
"""
    else:
        source_instruction = f"""
SOURCE STATUS:
Live web search snippets do not clearly confirm or deny the central claim.
For text/headline mode, unclear evidence usually means INSUFFICIENT EVIDENCE.
For credible URL mode, also consider the submitted article itself as primary evidence.
"""

    factcheck_instruction = """
FACT-CHECK PRIORITY RULE:
- If a fact-check source says the claim is misleading, missing context, old, miscaptioned, misrepresented, fabricated, or false, prioritize that fact-check over general news results.
- If Reuters, AP Fact Check, Snopes, PolitiFact, Full Fact, AFP Fact Check, BOOM, Alt News, or Logically Facts directly corrects the claim, do not mark the claim SUPPORTED.
"""

    DYNAMIC_PROMPT = f"""You are an expert fact-checker analyzing claims against submitted article evidence and live web search results.

CRITICAL CONTEXT:
Today's date is {current_date}.

INPUT TYPE:
{input_type}

CLAIM / ARTICLE TEXT TO ANALYZE:
{text}

LIVE WEB SEARCH RESULTS:
{live_context}

{domain_instruction}

{url_instruction}

{source_instruction}

{factcheck_instruction}

ANALYSIS INSTRUCTIONS:

1. IDENTIFY THE CENTRAL CLAIM
   - Determine the main subject.
   - Determine the main action/event.
   - Determine whether the claim includes a cause/reason, such as "because" or "due to".
   - Ignore minor wording differences, but do not ignore changed meaning.

2. CHECK THE SUBMITTED ARTICLE AND LIVE SOURCES
   - In URL mode, the submitted article is primary evidence.
   - In text/headline mode, live search results are the main evidence.
   - Check whether sources support, contradict, or only mention related topics.
   - For video/photo claims, check if the media is old, miscaptioned, or from a different event/location.

3. EVALUATE CREDIBILITY
   - Recognized credible news source + routine reporting = stronger evidence.
   - Unknown source + no external confirmation = weak evidence.
   - Extraordinary or high-risk claims require stronger evidence.
   - Sports/general entertainment reporting can be supported with moderate confidence from one credible article.
   - Medical/health claims need scientific or fact-check support.

4. ASSESS LANGUAGE PATTERNS
   - Professional, measured language = good sign.
   - Sensationalist urgency, conspiracy framing, miracle claims = red flags.
   - Lack of exact snippet repetition is not automatically a red flag.

VERDICT LABELS:
- SUPPORTED: credible evidence supports the central claim.
- REFUTED: credible evidence contradicts or denies the central claim.
- INSUFFICIENT EVIDENCE: evidence does not clearly confirm or deny the claim.
- MISLEADING: claim contains some truth but exaggerates, omits key context, uses old/miscaptioned media, or frames evidence unfairly.
- LOW CREDIBILITY: claim has suspicious language, weak sourcing, or risky patterns, but cannot be directly refuted.

STRICT RULES:
- Do NOT use REAL or FAKE.
- Do NOT mark SUPPORTED from topic overlap alone.
- Do NOT over-penalize credible URL articles just because live-search snippets are short.
- In URL mode, if a credible article directly reports a routine sports/general claim and no contradiction is found, SUPPORTED with 70-82 confidence is acceptable.
- For health, death, arrest, election, finance, and public-safety claims, require stronger corroboration.
- If sources mention the person/company/topic but not the exact event, and there is no credible submitted URL, choose INSUFFICIENT EVIDENCE.
- If the claim uses causal wording like "because", "due to", "dropped because", or "removed because", sources must support that specific reason; same-topic articles are not enough.
- If a fact-check source says the claim is misleading, missing context, old, miscaptioned, misrepresented, fabricated, or false, prioritize that fact-check over general news results.
- If the claim sounds suspicious but sources do not clearly refute it, choose LOW CREDIBILITY.

CONFIDENCE SCORING:
- Strong direct support from multiple credible sources → 85-95
- Credible submitted URL supports routine claim, no contradiction → 70-82
- Strong direct contradiction from credible sources → 80-95
- Fact-check says misleading/missing context → 75-90
- Partial truth / missing context → 60-80
- Weak sourcing or suspicious language → 50-75
- No clear evidence → 35-60

RED FLAG EXAMPLES:
- "Contradicts credible sources"
- "Fact-check source reports missing context"
- "Old or miscaptioned media"
- "Conspiracy theory language detected"
- "Unverifiable health miracle claim"
- "Sensationalist urgency language"
- "Unknown source with no external corroboration"

NOT red flags:
- "Lacks hyperlinks"
- "Missing exact search snippet"
- "Professional tone"

Respond ONLY with valid JSON:
{{
  "verdict": "SUPPORTED" or "REFUTED" or "INSUFFICIENT EVIDENCE" or "MISLEADING" or "LOW CREDIBILITY",
  "confidence": <0-100>,
  "reason": "<One clear sentence conclusion>",
  "fact_check": "<Brief evidence summary: what supports, refutes, or fails to prove the claim>",
  "red_flags": ["<only serious issues>"],
  "recommendations": ["<action1>"]
}}
"""

    payload = json.dumps({
        "model": config.COHERE_MODEL,
        "messages": [
            {"role": "system", "content": DYNAMIC_PROMPT},
            {"role": "user", "content": "Analyze this claim based on the evidence provided above."}
        ],
        "temperature": 0.0,
        "max_tokens": 700,
    }).encode("utf-8")

    req = urllib.request.Request(
        config.COHERE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.COHERE_API_KEY}",
            "X-Client-Name": "debunkit"
        },
        method="POST"
    )

    try:
        logger.info(
            f"Sending request to Cohere API "
            f"(attempt {retry_count + 1}/{max_retries + 1})..."
        )

        with urllib.request.urlopen(req, timeout=config.COHERE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        raw = data["message"]["content"][0]["text"].strip()

        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed_result = json.loads(raw.strip())

        parsed_result["verdict"] = normalize_verdict(parsed_result.get("verdict"))
        parsed_result["confidence"] = clamp_confidence(parsed_result.get("confidence"), default=55)
        parsed_result["sources"] = merge_sources(source_url, source_links)

        # Fact-check override:
        # If a trusted fact-check result clearly refutes or corrects the claim,
        # do not let the model mark the same-topic claim as SUPPORTED.
        if factcheck_override:
            logger.info(
                f"Fact-check override applied: {factcheck_override['verdict']} "
                f"({factcheck_override['confidence']}%)"
            )

            parsed_result["verdict"] = factcheck_override["verdict"]
            parsed_result["confidence"] = factcheck_override["confidence"]
            parsed_result["reason"] = factcheck_override["reason"]
            parsed_result["fact_check"] = factcheck_override["fact_check"]

            old_flags = parsed_result.get("red_flags", [])
            if not isinstance(old_flags, list):
                old_flags = []

            parsed_result["red_flags"] = list(dict.fromkeys(
                factcheck_override["red_flags"] + old_flags
            ))[:6]

            logger.info(
                f"[OK] Cohere analysis successful after fact-check override: "
                f"{parsed_result.get('verdict')} ({parsed_result.get('confidence')}% confidence)"
            )

            return parsed_result

        # Confidence boost when AI and source matcher agree.
        if confirmation_status == "supported" and parsed_result["verdict"] == "SUPPORTED":
            parsed_result["confidence"] = min(parsed_result["confidence"] + 8, 95)

        if confirmation_status == "refuted" and parsed_result["verdict"] in {"REFUTED", "MISLEADING"}:
            parsed_result["confidence"] = min(parsed_result["confidence"] + 8, 95)

        # Prevent overconfidence if text/headline mode has weak evidence.
        if (
            input_type != "url"
            and confirmation_status == "insufficient"
            and parsed_result["verdict"] == "SUPPORTED"
        ):
            parsed_result["confidence"] = min(parsed_result["confidence"], 70)
            parsed_result["fact_check"] = (
                str(parsed_result.get("fact_check", "")) +
                " Source matcher did not find strong explicit confirmation; treat this as tentative."
            ).strip()

        # Causal-claim guard:
        # If the model says supported but the claim contains a specific reason/cause
        # and our source matcher did not strongly confirm it, downgrade.
        if (
            input_type != "url"
            and causal_claim
            and confirmation_status != "supported"
            and parsed_result["verdict"] == "SUPPORTED"
        ):
            logger.info("Causal claim guard applied.")

            parsed_result["verdict"] = "INSUFFICIENT EVIDENCE"
            parsed_result["confidence"] = min(parsed_result["confidence"], 55)
            parsed_result["reason"] = (
                "The sources mention the topic, but do not clearly confirm the specific reason or cause stated in the claim."
            )
            parsed_result["fact_check"] = (
                "Same-topic sources are not enough for causal claims. The claim needs direct evidence for the stated reason."
            )

            red_flags = parsed_result.get("red_flags", [])
            if not isinstance(red_flags, list):
                red_flags = []

            parsed_result["red_flags"] = list(dict.fromkeys(
                ["Specific cause/reason not directly supported"] + red_flags
            ))[:6]

        # URL-mode rescue:
        # A recognized credible URL reporting routine sports/general news should not be marked
        # insufficient only because external search snippets are incomplete.
        if (
            input_type == "url"
            and source_url
            and submitted_url_is_credible
            and not high_risk_claim
            and claim_type in {"sports", "general"}
            and confirmation_status != "refuted"
            and parsed_result["verdict"] == "INSUFFICIENT EVIDENCE"
            and parsed_result["confidence"] <= 65
        ):
            logger.info("URL-mode credible-source rescue applied.")

            parsed_result["verdict"] = "SUPPORTED"
            parsed_result["confidence"] = max(parsed_result["confidence"], 74)
            parsed_result["reason"] = (
                "The submitted article was successfully retrieved from a recognized news source "
                "and directly reports the routine claim."
            )
            parsed_result["fact_check"] = (
                "The submitted article itself provides primary support for the claim. "
                "Live search snippets did not clearly contradict it, but external corroboration "
                "was limited, so confidence remains moderate."
            )

            red_flags = parsed_result.get("red_flags", [])
            if not isinstance(red_flags, list):
                red_flags = []

            filtered_flags = []
            for flag in red_flags:
                flag_text = str(flag).lower()
                if "snippet" in flag_text or "hyperlink" in flag_text or "missing exact" in flag_text:
                    continue
                filtered_flags.append(flag)

            parsed_result["red_flags"] = filtered_flags

        logger.info(
            f"[OK] Cohere analysis successful: "
            f"{parsed_result.get('verdict')} ({parsed_result.get('confidence')}% confidence)"
        )

        return parsed_result

    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning(
            f"Network/Timeout error "
            f"(attempt {retry_count + 1}/{max_retries + 1}): {e}"
        )

        if retry_count < max_retries:
            logger.info(f"Retrying AI analysis... ({retry_count + 1}/{max_retries})")
            return ai_analyze(
                text,
                input_type=input_type,
                source_url=source_url,
                source_text=source_text,
                retry_count=retry_count + 1,
                max_retries=max_retries
            )

        logger.error(
            f"AI analysis failed after {max_retries + 1} attempts. "
            "Falling back to local NLP."
        )
        return None

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
        except Exception:
            error_body = ""

        logger.error(f"HTTP error from Cohere ({e.code}): {error_body}")

        if e.code == 401:
            logger.error("Authentication failed. Check your Cohere API key.")
            return None

        if retry_count < max_retries:
            logger.info("Retrying AI analysis...")
            return ai_analyze(
                text,
                input_type=input_type,
                source_url=source_url,
                source_text=source_text,
                retry_count=retry_count + 1,
                max_retries=max_retries
            )

        return None

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Cohere response as JSON: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error in AI analysis: {e}")
        return None


# ===== HYBRID ANALYSIS =====

def hybrid_analyze(text, input_type="text", source_url=None, source_text=None):
    """
    Perform analysis with AI priority, fallback to local NLP only.
    """
    logger.info("Starting analysis...")

    ai = ai_analyze(
        text,
        input_type=input_type,
        source_url=source_url,
        source_text=source_text
    )

    if ai:
        logger.info(
            f"[OK] AI analysis successful: "
            f"{ai['verdict']} ({ai['confidence']}% confidence)"
        )

        return {
            "verdict": normalize_verdict(ai.get("verdict")),
            "confidence": clamp_confidence(ai.get("confidence"), default=55),
            "reason": ai.get("reason", ""),
            "fact_check": ai.get("fact_check", ""),
            "red_flags": ai.get("red_flags", [])[:6],
            "recommendations": ai.get("recommendations", []),
            "sources": ai.get("sources", []),
            "mode": "ai"
        }

    logger.info("[WARNING] AI analysis failed. Falling back to local NLP analysis...")

    local = local_analyze(text)

    net = local["net_score"]
    claim_flags = local["claim_flags"]
    credible_hits = local["credible_hits"]

    fake_threshold_local = getattr(config, "FAKE_THRESHOLD_LOCAL", 35)
    min_credible_hits = getattr(config, "MIN_CREDIBLE_HITS", 2)

    if net >= fake_threshold_local or (claim_flags and credible_hits < min_credible_hits):
        verdict = "LOW CREDIBILITY"
        confidence = min(50 + net // 2, 85)
        reason = claim_flags[0] if claim_flags else "Multiple misinformation-risk patterns were detected."

    elif credible_hits >= min_credible_hits:
        verdict = "INSUFFICIENT EVIDENCE"
        confidence = min(45 + credible_hits * 5, 65)
        reason = "Some credibility signals were found, but live source verification was unavailable."

    else:
        verdict = "INSUFFICIENT EVIDENCE"
        confidence = 50
        reason = "AI/source verification was unavailable, so the claim cannot be confirmed."

    fallback_sources = []
    if input_type == "url" and source_url:
        fallback_sources.append({
            "title": "Submitted article",
            "url": source_url
        })

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "fact_check": "AI analysis unavailable — using local pattern analysis only.",
        "red_flags": local["red_flags"],
        "recommendations": ["Connect to internet for more accurate AI-powered fact-checking"],
        "sources": fallback_sources,
        "mode": "local_fallback"
    }