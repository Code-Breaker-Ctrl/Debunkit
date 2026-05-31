# Core/nlp_engine.py
import re
import logging

logger = logging.getLogger(__name__)


LIVING_PUBLIC_FIGURES = [
    # Indian Politicians
    "narendra modi", "modi", "amit shah", "rahul gandhi", "sonia gandhi",
    "mamata banerjee", "arvind kejriwal", "yogi adityanath",
    "rajnath singh", "nirmala sitharaman", "s jaishankar", "piyush goyal",
    "anurag thakur", "subrahmanyam jaishankar",
    
    # International Politicians
    "donald trump", "joe biden", "kamala harris", "vladimir putin",
    "xi jinping", "rishi sunak", "emmanuel macron", "justin trudeau",
    "olaf scholz", "giorgia meloni",
    
    # Business Leaders
    "elon musk", "mark zuckerberg", "sundar pichai", "tim cook",
    "jeff bezos", "bill gates", "sam altman", "jensen huang",
    "satya nadella", "bob iger", "tim armstrong",
    
    # Religious/Monarchy
    "pope francis", "king charles", "prince william", "meghan",
    "princess kate", "prince harry",
    
    # Other Notable Figures
    "andrew tate", "kylie jenner", "taylor swift", "oprah winfrey",
    "kanye west", "kim kardashian", "johnny depp", "amber heard",
]

HIGH_RISK_VERBS = [
    "died", "dead", "passed away", "killed", "assassinated", "murdered",
    "arrested", "jailed", "imprisoned", "resigned", "fired", "removed",
    "impeached", "overthrown", "hospitalized", "collapsed",
    "shot", "stabbed", "poisoned", "heart attack", "stroke"
]


FAKE_PATTERNS = {
    "sensationalist": {
        "patterns": [
            "shocking", "bombshell", "explosive", "exposed", "leaked",
            "banned", "censored", "suppressed", "they don't want",
            "mainstream media refuses", "share before", "share this now",
            "wake up", "truth revealed", "cover-up", "coverup"
        ],
        "weight": 12,
        "description": "Sensationalist language commonly used in clickbait"
    },
    "conspiracy": {
        "patterns": [
            "they are hiding", "shadow government", "mind control",
            "microchip", "5g causes", "vaccine causes", "chemtrails",
            "population control", "depopulation", "globalist", "false flag",
            "inside job", "staged attack", "crisis actors", "staged"
        ],
        "weight": 22,
        "description": "Conspiracy theory language"
    },
    "urgency": {
        "patterns": [
            "share immediately", "before it's deleted", "before they delete",
            "spread the word", "everyone needs to know", "tell everyone",
            "repost now", "they're trying to silence", "urgent"
        ],
        "weight": 15,
        "description": "Artificial urgency to bypass critical thinking"
    },
    "pseudoscience": {
        "patterns": [
            "miracle cure", "doctors hate", "one weird trick",
            "big pharma doesn't want", "100% effective", "guaranteed cure",
            "instantly cures", "eliminates cancer", "drinking bleach",
            "crystals heal", "quantum healing", "alternative medicine cures all"
        ],
        "weight": 25,
        "description": "Pseudoscientific health claims"
    },
    "absolute": {
        "patterns": [
            "100% proven", "undeniable proof", "definitive proof",
            "always works", "never fails", "guaranteed to", "all doctors agree"
        ],
        "weight": 10,
        "description": "Absolute claims without nuance"
    },
}


CREDIBLE_PATTERNS = [
    (r'\baccording to\s+(?:an?\s+)?(?:official\s+)?(?:statement|announcement|press release|report)\b', "official source"),
    (r'\bresearchers? (?:at|from)?\s+\w+\s+(?:found|say|report|discovered)\b', "academic reference"),
    (r'\b(?:peer.?reviewed|published in|journal of)\b', "peer review"),
    (r'\b(?:university|college|institute|research center)\b', "academic institution"),
    (r'\bofficial\s+(?:statement|report|data|announcement)\b', "official source"),
    (r'\b(?:reuters|associated press|ap news|bbc|cnn|nyt)\b', "major news outlet"),
    (r'\bgovernment (?:said|announced|reported|confirmed)\b', "government source"),
    (r'\bspokesperson\s+(?:said|stated)\b', "official spokesperson"),
    (r'\bstudies? (?:show|suggest|indicate|found)\b', "research reference"),
    (r'\bexperts? (?:say|warn|note|suggest|confirmed)\b', "expert attribution"),
    (r'\bdata (?:shows|indicates|suggests)\b', "data reference"),
    (r'\b(?:could|might|may|possibly|reportedly|allegedly|appears to)\b', "hedging language"),
    (r'\bdespite|however|although|though\b', "hedging language"),
    (r'"[^"]{10,}"', "direct quote"),
    (r'\b(?:Dr\.|Professor|Prof\.|PhD)\s+[A-Z]\w+\b', "credential"),
    (r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', "specific date"),
    (r'\b(?:Stanford|Harvard|MIT|Yale|Oxford|Cambridge|Berkeley)\b', "prestigious institution"),
]

SOURCE_SIGNALS = [
    r'\baccording to\b',
    r'\bofficial\b',
    r'\bconfirmed by\b',
    r'\bannounced by\b',
    r'\breported by\b',
    r'\bsources say\b',
    r'\bsaid in a statement\b',
    r'\bpress conference\b',
]

def detect_unverified_claims(text):
    """
    Detect unverified claims about public figures.
    
    Args:
        text: Full text to analyze
    
    Returns:
        list: List of flagged unverified claims with context
    """
    text_lower = text.lower()
    flags = []
    
    for figure in LIVING_PUBLIC_FIGURES:
        if figure in text_lower:
            # Find all occurrences
            idx = 0
            while True:
                idx = text_lower.find(figure, idx)
                if idx == -1:
                    break
                
                # Extract context window: 100 chars before and after
                context_start = max(0, idx - 100)
                context_end = min(len(text_lower), idx + 100 + len(figure))
                window = text_lower[context_start:context_end]
                
                # Check for high-risk verbs in window
                for verb in HIGH_RISK_VERBS:
                    if verb in window:
                        # Check if credible source is cited
                        has_source = any(re.search(p, window) for p in SOURCE_SIGNALS)
                        
                        if not has_source:
                            # Extract the problematic sentence
                            sentence_match = re.search(
                                r'[^.!?]*' + re.escape(figure) + r'[^.!?]*[.!?]',
                                text[max(0, idx-200):idx+200],
                                re.IGNORECASE
                            )
                            claim_context = sentence_match.group().strip() if sentence_match else "..."
                            
                            flag = (
                                f"⚠ Unverified claim about '{figure.title()}': "
                                f"mentions '{verb}' without credible source attribution. "
                                f"Context: '{claim_context[:80]}...'"
                            )
                            flags.append(flag)
                
                idx += len(figure)
    
    return flags

def local_analyze(text):
    """
    Perform comprehensive local NLP analysis.
    
    Scoring breakdown:
    - Fake Score: Points added for misinformation patterns
    - Credible Score: Points added for credibility indicators
    - Net Score: fake_score - credible_score (normalized 0-100)
    
    Args:
        text: Text to analyze
    
    Returns:
        dict: Detailed analysis with scores and flags
    """
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    
    red_flags = []
    fake_score = 0
    credible_hits = 0
    
    logger.debug(f"Starting local analysis: {word_count} words, {len(sentences)} sentences")
    
    # ===== UNVERIFIED CLAIMS CHECK =====
    claim_flags = detect_unverified_claims(text)
    if claim_flags:
        # Each unverified claim about public figures is +45 to fake_score
        fake_score += 45 * len(claim_flags)
        red_flags.extend(claim_flags)
        logger.debug(f"Detected {len(claim_flags)} unverified claims")
    
    # ===== MISINFORMATION PATTERN CHECK =====
    # Documented weights applied per pattern category
    for category, config_data in FAKE_PATTERNS.items():
        patterns = config_data["patterns"]
        weight = config_data["weight"]
        description = config_data["description"]
        
        found = [p for p in patterns if p in text_lower]
        if found:
            # Add score: minimum of (count * weight) and 45 to avoid overcounting
            score_addition = min(len(found) * weight, 45)
            fake_score += score_addition
            
            # Create descriptive flag with top patterns
            flag_text = f"🚩 {description}: {', '.join(found[:3])}"
            if len(found) > 3:
                flag_text += f" (+{len(found)-3} more)"
            
            red_flags.append(flag_text)
            logger.debug(f"Found {len(found)} {category} patterns (score +{score_addition})")
    
    # ===== CREDIBILITY PATTERN CHECK =====
    for pattern, description in CREDIBLE_PATTERNS:
        if re.search(pattern, text_lower):
            credible_hits += 1
            logger.debug(f"Found credibility pattern: {description}")
    
    # Credible score: min of (hits * 8) and 55
    credible_score = min(credible_hits * 8, 55)
    
    # ===== CLICKBAIT OPENING CHECK =====
    first_sentence = sentences[0] if sentences else text[:120]
    if re.search(r'^(BREAKING|URGENT|ALERT|SHOCKING|EXPOSED)', first_sentence, re.I):
        fake_score += 20
        red_flags.append("📰 Clickbait-style opening (BREAKING, URGENT, ALERT, etc.)")
        logger.debug("Detected clickbait opening")
    
    # ===== EXCESSIVE CAPITALIZATION CHECK =====
    caps = re.findall(r'\b[A-Z]{3,}\b', text)
    cap_ratio = len(caps) / max(word_count, 1)
    if cap_ratio > 0.08:  # More than 8% all-caps words
        fake_score += 15
        red_flags.append(f"🔤 Excessive capitalization ({len(caps)} all-caps words, {cap_ratio*100:.1f}%)")
        logger.debug(f"Excessive capitalization detected: {cap_ratio*100:.1f}%")
    
    # ===== EXCESSIVE PUNCTUATION CHECK =====
    exclamation_count = text.count('!')
    if exclamation_count >= 2:
        fake_score += 10
        red_flags.append(f"❗ Excessive exclamation marks ({exclamation_count} found)")
        logger.debug(f"Excessive exclamation marks: {exclamation_count}")
    
    # ===== HEDGING LANGUAGE CHECK =====
    hedging_words = re.findall(r'\b(could|might|may|possibly|reportedly|allegedly|suggests|appears)\b', text_lower)
    if word_count > 50 and not hedging_words:
        fake_score += 10
        red_flags.append("⚖️ No hedging language (absolute claims without qualification)")
        logger.debug("No hedging language detected in long text")
    
    # ===== FINAL SCORE CALCULATION =====
    # Net score = fake - credible (normalized to 0-100)
    net_score = max(0, min(fake_score - credible_score, 100))
    
    logger.info(
        f"Local analysis complete: fake_score={fake_score}, "
        f"credible_score={credible_score}, net_score={net_score}, "
        f"red_flags={len(red_flags)}"
    )
    
    return {
        "net_score": net_score,
        "fake_score": fake_score,
        "credible_score": credible_score,
        "credible_hits": credible_hits,
        "red_flags": red_flags[:5],  # Top 5 flags
        "claim_flags": claim_flags,
    }