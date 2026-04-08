"""
Improved AI engine for Debunkit fact-checking.

Key improvements over the original engine:
- Domain-aware prompting (sports / politics / health / general)
- Better source-matching logic (CONFIRM → REAL, CONTRADICT → FAKE)
- Smarter confidence scoring based on source quality
- Reduced paranoia (no penalty for professional language)
- Red flags only for genuine issues
"""

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain detection helpers
# ---------------------------------------------------------------------------

_SPORTS_KEYWORDS = {
    "cricket", "ipl", "t20", "odi", "test match", "match", "team", "player",
    "score", "scorecard", "tournament", "world cup", "football", "tennis",
    "basketball", "batting", "bowling", "wicket", "wickets", "goal", "goals",
    "runs", "innings", "over", "overs", "fifa", "icc", "bcci", "premier league",
    "champions league", "ashes", "series", "cup final", "slam", "grand prix",
}

_POLITICS_KEYWORDS = {
    "government", "minister", "election", "parliament", "president",
    "prime minister", "vote", "policy", "law", "bill", "senate", "congress",
    "party", "mp", "mla", "cabinet", "constitution", "court", "judiciary",
    "ruling", "opposition", "coalition", "governor",
}

_HEALTH_KEYWORDS = {
    "cure", "treatment", "disease", "vaccine", "vaccination", "medicine",
    "hospital", "doctor", "health", "medical", "cancer", "virus", "infection",
    "drug", "clinical", "study", "trial", "pandemic", "epidemic", "symptom",
    "diagnosis", "surgery", "therapy", "pill", "supplement", "side effect",
}


def detect_domain(text: str) -> str:
    """Return 'sports', 'politics', 'health', or 'general'."""
    words = set(re.findall(r'\b\w+\b', text.lower()))
    if words & _SPORTS_KEYWORDS:
        return "sports"
    if words & _HEALTH_KEYWORDS:
        return "health"
    if words & _POLITICS_KEYWORDS:
        return "politics"
    return "general"


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

_DOMAIN_INSTRUCTIONS: dict[str, str] = {
    "sports": (
        "SPORTS EVALUATION RULES:\n"
        "- Accept match reports, scorecards, sports-news articles, and live tickers "
        "as valid confirmation — do NOT require official press releases.\n"
        "- If multiple sports sources confirm the same result, score, or event → REAL.\n"
        "- If sources show a conflicting result (different winner / score) → FAKE.\n"
        "- Routine match results reported by credible sports outlets need no further proof.\n"
        "- Do NOT flag professional match-report language as suspicious."
    ),
    "politics": (
        "POLITICAL EVALUATION RULES:\n"
        "- Accept credible news agencies (Reuters, AP, BBC, PTI, The Hindu, etc.) as "
        "valid confirmation.\n"
        "- Verify against official statements when available, but a single credible "
        "outlet is sufficient for routine political news.\n"
        "- Watch for satire sites or opinion pieces mistaken as news.\n"
        "- Extraordinary claims (e.g., coups, assassinations) require multiple sources."
    ),
    "health": (
        "HEALTH/MEDICAL EVALUATION RULES:\n"
        "- Require scientific evidence or established medical consensus (WHO, CDC, "
        "peer-reviewed journals).\n"
        "- Be highly sceptical of miracle cures, '100% effective', or "
        "'doctors hate this' language.\n"
        "- A single unverified blog post is NOT sufficient confirmation.\n"
        "- Red-flag words: 'instant cure', 'guaranteed', 'they don't want you to know'."
    ),
    "general": (
        "GENERAL EVALUATION RULES:\n"
        "- Accept credible news sources as confirmation.\n"
        "- Do NOT require multiple independent sources for routine news.\n"
        "- Balance caution with practicality — avoid marking obvious facts as UNCERTAIN.\n"
        "- Professional, measured language is NOT suspicious."
    ),
}


def _build_prompt(text: str, sources: list[dict], domain: str) -> str:
    """Build the domain-aware fact-checking prompt sent to the LLM."""
    domain_block = _DOMAIN_INSTRUCTIONS.get(domain, _DOMAIN_INSTRUCTIONS["general"])

    if sources:
        sources_block = "LIVE WEB SOURCES:\n" + "\n".join(
            f"{i}. [{s.get('title', 'No title')}] {s.get('snippet', '')}"
            for i, s in enumerate(sources[:5], 1)
        )
    else:
        sources_block = "No live web sources were found for this claim."

    return f"""You are a professional, no-nonsense fact-checker. Analyse the claim below and \
return EXACTLY one JSON object — nothing else.

CLAIM: "{text}"

DOMAIN: {domain.upper()}

{domain_block}

{sources_block}

SOURCE MATCHING RULES (in priority order):
1. Sources EXPLICITLY confirm the claim (names, scores, dates match) → verdict REAL, \
confidence 88-95.
2. Sources confirm the claim in general terms → verdict REAL, confidence 82-88.
3. Sources CONTRADICT the claim (different winner, wrong date, explicitly false) → verdict FAKE, \
confidence 82-95.
4. Sources exist but are ambiguous or unrelated → verdict UNCERTAIN, confidence 45-60.
5. No sources found AND claim contains suspicious language (see below) → verdict FAKE, \
confidence 70-85.
6. No sources found AND claim is plausible / routine → verdict UNCERTAIN, confidence 50-65.

RED FLAG RULES — only flag genuine problems:
- A source explicitly calls the claim false or misleading.
- The claim contradicts well-known scientific or historical facts.
- Sensationalist language: "you won't believe", "shocking truth", "they're hiding".
- Health claim uses miracle-cure language without any scientific backing.
DO NOT flag: professional tone, lack of hyperlinks in the text, absence of quotes, \
or the fact that the claim is short.

CONFIDENCE GUIDE:
- Sources explicitly confirm with specific details (names, scores, dates): 90-95
- Sources confirm generally: 82-90
- Sources contradict: 82-95
- Mixed/ambiguous sources: 45-60
- No sources, plausible claim: 50-65
- No sources, suspicious claim: 70-85

Respond with this JSON schema and NO other text:
{{
  "verdict": "REAL" | "FAKE" | "UNCERTAIN",
  "confidence": <integer 0-100>,
  "summary": "<one concise sentence explaining the verdict>",
  "red_flags": ["<specific problem>", ...],
  "source_analysis": "<how the sources support or contradict the claim>"
}}"""


# ---------------------------------------------------------------------------
# Local (heuristic) fallback analysis
# ---------------------------------------------------------------------------

_SENSATIONAL_PATTERNS = [
    r"you won'?t believe",
    r"shocking(ly)?",
    r"they don'?t want you to know",
    r"breaking(:\s|\s)",
    r"doctors hate",
    r"one weird trick",
    r"secret(ly)? revealed",
]

_HEALTH_MIRACLE_PATTERNS = [
    r"\bcure\b",
    r"\bmiracle\b",
    r"\binstant\b.{0,20}\bcure\b",
    r"\bguaranteed\b",
    r"100\s*%\s*(effective|cure)",
]

_CONTRADICTION_WORDS = {
    "false", "fake", "incorrect", "wrong", "denied", "untrue", "misleading",
    "debunked", "hoax", "myth", "fabricated", "no evidence",
}


def _word_overlap(text_a: str, text_b: str) -> float:
    """Fraction of meaningful words in text_a that also appear in text_b."""
    words_a = set(re.findall(r'\b[a-z]{4,}\b', text_a.lower()))
    words_b = set(re.findall(r'\b[a-z]{4,}\b', text_b.lower()))
    if not words_a:
        return 0.0
    return len(words_a & words_b) / len(words_a)


def _extract_named_entities(text: str) -> set[str]:
    """Extract capitalised words/phrases as a rough proxy for named entities."""
    return set(re.findall(r'\b[A-Z][a-z]{2,}\b', text))


def _entity_conflict(claim: str, src_text: str, src_title: str) -> bool:
    """
    Detect when a source is about the same *event* as the claim but credits a
    different *actor* (e.g. source says 'India wins Cup' but claim says
    'Pakistan wins Cup').

    Heuristic: if the source title/snippet explicitly names one entity as the
    winner/achiever, check whether the claim names a *different* entity for
    the same role.
    """
    claim_entities = _extract_named_entities(claim)
    src_entities   = _extract_named_entities(src_title + " " + src_text)

    # Words that indicate the subject of a result (winner, achiever, etc.)
    achievement_verbs = {
        "wins", "won", "beat", "beats", "defeated", "defeats",
        "clinches", "clinched", "bags", "bagged", "takes", "took",
        "crowned", "champions",
    }

    src_words = set(src_text.lower().split()) | set(src_title.lower().split())
    if not (src_words & achievement_verbs):
        return False  # source is not about a result

    # Entities present in source but absent from claim (and vice-versa)
    src_only  = src_entities - claim_entities
    claim_only = claim_entities - src_entities

    # Conflict: source credits one entity, claim credits a different entity
    return bool(src_only) and bool(claim_only)


def _heuristic_analyse(text: str, sources: list[dict], domain: str) -> dict:
    """
    Heuristic fallback used when no LLM is available.

    Returns a result dict matching the schema returned by the LLM path.
    """
    text_lower = text.lower()

    # ---- source evaluation ----
    confirmed = False
    contradicted = False
    source_notes: list[str] = []

    for src in sources[:5]:
        src_title  = src.get("title", "")
        src_snippet = src.get("snippet", "")
        src_text   = (src_title + " " + src_snippet).lower()
        overlap    = _word_overlap(text_lower, src_text)

        # Check for explicit contradiction words
        has_explicit_contradiction = bool(_CONTRADICTION_WORDS & set(src_text.split()))

        # Check for entity-level conflict (e.g. India won vs Pakistan won)
        has_entity_conflict = _entity_conflict(text, src_snippet, src_title)

        if overlap > 0.35:
            if has_explicit_contradiction or has_entity_conflict:
                contradicted = True
                source_notes.append(f"Contradicted by: {src_title or 'source'}")
            else:
                confirmed = True
                source_notes.append(f"Confirmed by: {src_title or 'source'}")
        elif overlap > 0.15 and (has_explicit_contradiction or has_entity_conflict):
            contradicted = True
            source_notes.append(f"Related source contradicts: {src_title or 'source'}")

    source_analysis = "; ".join(source_notes) if source_notes else (
        "Sources found but no clear relationship to the claim."
        if sources else "No web sources found."
    )

    # ---- red flags ----
    red_flags: list[str] = []

    for pattern in _SENSATIONAL_PATTERNS:
        if re.search(pattern, text_lower):
            red_flags.append(f"Sensationalist language detected: '{pattern}'")

    if domain == "health":
        for pattern in _HEALTH_MIRACLE_PATTERNS:
            if re.search(pattern, text_lower):
                red_flags.append("Health claim uses miracle-cure language")
                break

    # ---- verdict ----
    if contradicted and not confirmed:
        return {
            "verdict": "FAKE",
            "confidence": 85,
            "summary": "Web sources contradict this claim.",
            "red_flags": red_flags or ["Claim contradicted by web sources"],
            "source_analysis": source_analysis,
            "domain": domain,
        }

    if confirmed and not contradicted:
        confidence = 88 if not red_flags else 78
        return {
            "verdict": "REAL",
            "confidence": confidence,
            "summary": "Claim confirmed by web sources.",
            "red_flags": red_flags,
            "source_analysis": source_analysis,
            "domain": domain,
        }

    if confirmed and contradicted:
        return {
            "verdict": "UNCERTAIN",
            "confidence": 50,
            "summary": "Sources give mixed signals about this claim.",
            "red_flags": red_flags,
            "source_analysis": source_analysis,
            "domain": domain,
        }

    # No matching sources
    if red_flags:
        confidence = 75 if domain == "health" else 70
        return {
            "verdict": "FAKE",
            "confidence": confidence,
            "summary": "No supporting sources found and the claim has suspicious characteristics.",
            "red_flags": red_flags,
            "source_analysis": source_analysis,
            "domain": domain,
        }

    return {
        "verdict": "UNCERTAIN",
        "confidence": 55,
        "summary": "Could not verify: no supporting or contradicting sources found.",
        "red_flags": [],
        "source_analysis": source_analysis,
        "domain": domain,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class AIEngine:
    """
    Improved fact-checking engine.

    Usage::

        engine = AIEngine()
        result = engine.analyse("India won the T20 World Cup 2024", sources=[...])
        # result = {
        #   "verdict": "REAL",
        #   "confidence": 92,
        #   "summary": "...",
        #   "red_flags": [],
        #   "source_analysis": "...",
        #   "domain": "sports"
        # }
    """

    def __init__(self) -> None:
        self._client = None
        self._setup_llm()

    def _setup_llm(self) -> None:
        """Initialise the OpenAI client if an API key is available."""
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            logger.info("OPENAI_API_KEY not set — using heuristic fallback.")
            return
        try:
            import openai  # noqa: PLC0415

            self._client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialised (model: gpt-4o-mini).")
        except ImportError:
            logger.warning("openai package not installed — using heuristic fallback.")

    # ------------------------------------------------------------------
    # Main entry-point
    # ------------------------------------------------------------------

    def analyse(self, text: str, sources: Optional[list[dict]] = None) -> dict:
        """
        Analyse a claim for truthfulness.

        Parameters
        ----------
        text:
            The claim/headline to fact-check.
        sources:
            Optional list of dicts with ``'title'`` and ``'snippet'`` keys
            representing live web search results.

        Returns
        -------
        dict
            ``{ verdict, confidence, summary, red_flags, source_analysis, domain }``
        """
        if not text or not text.strip():
            return {
                "verdict": "UNCERTAIN",
                "confidence": 0,
                "summary": "No claim provided.",
                "red_flags": ["Empty input"],
                "source_analysis": "N/A",
                "domain": "general",
            }

        sources = sources or []
        domain = detect_domain(text)

        if self._client is not None:
            return self._llm_analyse(text, sources, domain)
        return _heuristic_analyse(text, sources, domain)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_analyse(self, text: str, sources: list[dict], domain: str) -> dict:
        """Send the claim + sources to the LLM and parse the JSON response."""
        prompt = _build_prompt(text, sources, domain)
        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional fact-checker. "
                            "Respond with valid JSON only — no markdown, no prose."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=600,
            )
            raw = response.choices[0].message.content.strip()
            result = self._parse_json(raw)
            result.setdefault("domain", domain)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM analysis failed (%s) — falling back to heuristics.", exc)
            return _heuristic_analyse(text, sources, domain)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extract and parse the first JSON object found in *raw*."""
        # Strip optional markdown fences
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response: {raw!r}")
        data = json.loads(match.group())

        # Normalise verdict
        verdict = str(data.get("verdict", "UNCERTAIN")).upper()
        if verdict not in {"REAL", "FAKE", "UNCERTAIN"}:
            verdict = "UNCERTAIN"
        data["verdict"] = verdict

        # Clamp confidence
        try:
            data["confidence"] = max(0, min(100, int(data.get("confidence", 50))))
        except (TypeError, ValueError):
            data["confidence"] = 50

        # Ensure list fields
        data.setdefault("red_flags", [])
        data.setdefault("source_analysis", "")
        data.setdefault("summary", "")

        return data
