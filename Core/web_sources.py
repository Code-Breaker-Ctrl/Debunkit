"""
Web source searching for Debunkit fact-checking engine.

Tries, in order:
1. DuckDuckGo (duckduckgo-search library, no API key required)
2. Returns an empty list if no search backend is available.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def search_sources(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web for sources relevant to *query*.

    Returns a list of dicts with keys:
        - ``title``   (str)
        - ``snippet`` (str)
        - ``url``     (str, optional)
    """
    results = _ddg_search(query, max_results)
    if results:
        return results

    logger.warning("All search backends failed — returning empty source list.")
    return []


# ---------------------------------------------------------------------------
# Backend: DuckDuckGo
# ---------------------------------------------------------------------------

def _ddg_search(query: str, max_results: int) -> Optional[list[dict]]:
    """Search using the duckduckgo-search library."""
    try:
        from duckduckgo_search import DDGS  # noqa: PLC0415

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))

        results = []
        for item in raw:
            results.append(
                {
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                    "url": item.get("href", ""),
                }
            )
        logger.debug("DuckDuckGo returned %d results for query: %s", len(results), query)
        return results
    except ImportError:
        logger.info("duckduckgo-search not installed — skipping DDG backend.")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("DuckDuckGo search failed: %s", exc)
        return None
