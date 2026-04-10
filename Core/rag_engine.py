"""
RAG (Retrieval-Augmented Generation) engine.
Fetches live web search context for a given query.
"""
import logging
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)


def get_live_context(query, max_results=5):
    """
    Perform a DuckDuckGo web search and return:
      - A combined text snippet (for the AI prompt)
      - A list of source dicts  [{"title": ..., "url": ..., "snippet": ...}]
    Falls back gracefully when duckduckgo-search is unavailable.
    """
    sources = []
    snippets = []

    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        for r in results:
            title = r.get("title", "")
            href = r.get("href", r.get("url", ""))
            body = r.get("body", r.get("snippet", ""))
            sources.append({"title": title, "url": href, "snippet": body})
            snippets.append(f"Source: {title}\nURL: {href}\nSnippet: {body}")
    except ImportError:
        logger.warning("duckduckgo-search not installed – skipping live context.")
    except Exception as exc:
        logger.warning(f"Web search failed: {exc}")

    context_text = "\n\n".join(snippets) if snippets else "No live search results available."
    return context_text, sources
