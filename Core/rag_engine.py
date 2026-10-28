import re
import time
import logging
import threading
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from config import config
from utils.validators import validate_url_input, ValidationError

logger = logging.getLogger(__name__)

# In-memory search cache: query_hash -> (timestamp, context_block, sources)
_SEARCH_CACHE = {}
_CACHE_LOCK = threading.Lock()


def get_live_context(query):
    """
    Search the internet for live context.

    Optimized version:
    - High-performance in-memory TTL cache (prevents repeat rate-limiting)
    - Parallelized search queries using ThreadPoolExecutor
    - Streamlined 2-query strategy (direct claim + fact-check validation)
    - Resilient fallback on network/rate-limiting errors
    """
    logger.info(f"RAG Engine: Processing query with {len(query)} characters")

    # Check cache first
    cache_key = query.strip().lower()
    ttl = getattr(config, "RAG_CACHE_TTL_SECONDS", 3600)
    now = time.time()

    with _CACHE_LOCK:
        if cache_key in _SEARCH_CACHE:
            cached_time, cached_block, cached_sources = _SEARCH_CACHE[cache_key]
            if now - cached_time < ttl:
                logger.info("[*] RAG CACHE HIT: Serving context from memory")
                return cached_block, cached_sources
            else:
                del _SEARCH_CACHE[cache_key]

    def clean_query_text(text, max_words=14):
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split()
        return " ".join(words[:max_words])

    def build_entity_query(text):
        years = re.findall(r'\b20\d{2}\b', text)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', text)

        stop_words = {
            "The", "A", "An", "This", "That", "It", "In", "On", "If", "But",
            "And", "Or", "Is", "Are", "Was", "Were", "Has", "Have"
        }

        entities = [w for w in proper_nouns if w not in stop_words]

        important_lower_terms = re.findall(
            r'\b(video|photo|image|rally|cruise|hantavirus|outbreak|dropped|poor|fielding|'
            r'predicted|confirmed|inside|uk|london|stamford|street|simpsons)\b',
            text,
            re.I
        )

        keywords = list(dict.fromkeys(entities + years + important_lower_terms))
        return " ".join(keywords[:8])

    try:
        direct_query = clean_query_text(query)
        entity_query = build_entity_query(query)

        search_queries = []
        if direct_query.strip():
            search_queries.append(direct_query)
            search_queries.append(f"{direct_query} fact check")
        elif entity_query.strip():
            search_queries.append(entity_query)

        # Remove duplicate search queries
        search_queries = list(dict.fromkeys([q for q in search_queries if q.strip()]))[:2]

        if not search_queries:
            logger.warning("Could not extract meaningful search query")
            return "No extractable search terms found.", []

        logger.info(f"RAG search queries (parallelized): {search_queries}")

        all_results = []
        seen_urls = set()

        def fetch_ddg_results(search_query):
            query_results = []
            try:
                with DDGS() as ddgs:
                    # Fetch news first
                    try:
                        news_results = list(ddgs.news(search_query, max_results=4))
                    except Exception:
                        news_results = []

                    # Fetch text results
                    try:
                        text_results = list(ddgs.text(search_query, max_results=4))
                    except Exception:
                        text_results = []

                    for res in news_results + text_results:
                        res["_search_query"] = search_query
                        query_results.append(res)
            except Exception as search_err:
                logger.warning(f"DDG search worker failed for '{search_query}': {search_err}")
            return query_results

        # Execute searches concurrently
        with ThreadPoolExecutor(max_workers=len(search_queries)) as executor:
            future_to_query = {executor.submit(fetch_ddg_results, q): q for q in search_queries}
            for future in as_completed(future_to_query):
                for res in future.result():
                    url = res.get("url", res.get("href", "#"))
                    if not url or url == "#" or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_results.append(res)
                    if len(all_results) >= 8:
                        break

        if not all_results:
            logger.info("No search results found")
            return "No relevant web search results found for this query.", []

        context_block = "LIVE WEB SEARCH RESULTS:\n"
        sources = []

        for i, res in enumerate(all_results[:8], 1):
            title = res.get("title", "Unknown")
            body = res.get("body", res.get("snippet", ""))
            url = res.get("url", res.get("href", "#"))
            search_query_used = res.get("_search_query", "")

            body_preview = body[:650] + "..." if len(body) > 650 else body

            if url != "#":
                sources.append({
                    "title": title,
                    "url": url
                })

            context_block += (
                f"\n{i}. [{title}]\n"
                f"   URL: {url}\n"
                f"   Snippet: {body_preview}\n"
                f"   SearchQuery: {search_query_used}\n"
            )

        logger.info(f"RAG: Found {len(all_results)} results, extracted {len(sources)} valid sources")

        # Save to memory cache
        with _CACHE_LOCK:
            _SEARCH_CACHE[cache_key] = (now, context_block, sources)

        return context_block, sources

    except Exception as e:
        logger.exception(f"Unexpected error in RAG engine: {e}")
        return "Live web context unavailable due to search error.", []


def get_article_context_from_search(url):
    """
    Fallback retrieval: search web for article title/context if direct scrape fails.
    """
    try:
        parsed = urlparse(url)
        slug = re.sub(r'[-_/.]+', ' ', parsed.path).strip()
        search_terms = f"{parsed.netloc} {slug}".strip()
        if not search_terms or len(search_terms) < 5:
            search_terms = url

        logger.info(f"Fallback search context retrieval for query: {search_terms}")
        with DDGS() as ddgs:
            results = list(ddgs.text(search_terms, max_results=3))
            if not results:
                results = list(ddgs.text(url, max_results=3))

        if results:
            snippets = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                if title or body:
                    snippets.append(f"{title}. {body}")
            combined = " ".join(snippets)
            return combined, results
    except Exception as e:
        logger.warning(f"Fallback search context failed for {url}: {e}")
    return None, []


def scrape_article(url):
    """
    Scrape article content from a URL with robust headers, trailing-slash retries,
    and search-based context fallback.
    """
    logger.info(f"Scraper: Fetching URL - {url[:50]}...")

    try:
        url = validate_url_input(url)
    except ValidationError as e:
        error_msg = f"Blocked unsafe URL: {str(e)}"
        logger.warning(error_msg)
        return None, error_msg

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Upgrade-Insecure-Requests': '1',
    }

    response = None
    try:
        logger.debug(f"Fetching {url} with {config.SCRAPER_TIMEOUT}s timeout")
        response = requests.get(
            url,
            headers=headers,
            timeout=config.SCRAPER_TIMEOUT,
            allow_redirects=True
        )

        try:
            validate_url_input(response.url)
        except ValidationError as e:
            error_msg = f"Blocked unsafe redirect target: {str(e)}"
            logger.warning(f"{error_msg} | final_url={response.url}")
            return None, error_msg

        # If 404, try toggling trailing slash
        if response.status_code == 404:
            alt_url = url[:-1] if url.endswith('/') else url + '/'
            try:
                alt_resp = requests.get(
                    alt_url,
                    headers=headers,
                    timeout=config.SCRAPER_TIMEOUT,
                    allow_redirects=True
                )
                if alt_resp.status_code == 200:
                    response = alt_resp
            except Exception:
                pass

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, Exception) as fetch_err:
        logger.warning(f"Initial fetch failed for {url}: {fetch_err}")

    # If direct fetch succeeded (200), extract text from HTML
    article_text = None
    if response is not None and response.status_code == 200:
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()

            paragraphs = soup.find_all('p')
            if not paragraphs:
                article_text = soup.get_text()
            else:
                article_text = " ".join([p.get_text() for p in paragraphs])

            article_text = re.sub(r'\s+', ' ', article_text).strip()
            word_count = len(article_text.split())

            if word_count >= config.SCRAPER_MIN_WORDS:
                logger.info(f"Scraper: Successfully extracted {len(article_text)} characters ({word_count} words)")
                return article_text, None
            else:
                logger.info(f"Scraped text short ({word_count} words). Attempting search fallback.")
        except Exception as parse_err:
            logger.warning(f"Error parsing HTML: {parse_err}")

    # Fallback: Retrieve article context from search engine
    fallback_text, _ = get_article_context_from_search(url)
    if fallback_text and len(fallback_text.split()) >= config.SCRAPER_MIN_WORDS:
        logger.info(f"Scraper: Retrieved {len(fallback_text.split())} words from search context fallback")
        return fallback_text, None

    status_info = f" HTTP {response.status_code}" if response is not None else ""
    error_msg = f"Failed to fetch URL.{status_info}"
    return None, error_msg
