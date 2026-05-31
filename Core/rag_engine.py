import re
import logging
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from config import config
from utils.validators import validate_url_input, ValidationError

logger = logging.getLogger(__name__)

def get_live_context(query):
    """
    Search the internet for live context.

    Improved version:
    - Uses multiple search queries
    - Searches fact-check style queries
    - Keeps longer snippets
    - Deduplicates URLs
    """
    logger.info(f"RAG Engine: Processing query with {len(query)} characters")

    def clean_query_text(text, max_words=18):
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
        return " ".join(keywords[:10])

    try:
        direct_query = clean_query_text(query)
        entity_query = build_entity_query(query)

        search_queries = []

        if entity_query.strip():
            search_queries.append(entity_query)

        if direct_query.strip():
            search_queries.append(direct_query)
            search_queries.append(f'{direct_query} fact check false misleading')

        lower_query = query.lower()

        if any(word in lower_query for word in ["video", "photo", "image", "clip", "footage"]):
            search_queries.append(f'{direct_query} old video miscaptioned misleading fact check')

        if any(word in lower_query for word in ["hantavirus", "virus", "health", "outbreak"]):
            search_queries.append(f'{direct_query} Reuters Fact Check')

        # Remove duplicate search queries
        search_queries = list(dict.fromkeys([q for q in search_queries if q.strip()]))

        if not search_queries:
            logger.warning("Could not extract meaningful search query")
            return "No extractable search terms found.", []

        logger.info(f"RAG search queries: {search_queries}")

        all_results = []
        seen_urls = set()

        with DDGS() as ddgs:
            for search_query in search_queries:
                # News search
                try:
                    news_results = list(ddgs.news(search_query, max_results=4))
                except Exception as e:
                    logger.warning(f"News search failed for '{search_query}': {e}")
                    news_results = []

                # Text search
                try:
                    text_results = list(ddgs.text(search_query, max_results=4))
                except Exception as e:
                    logger.warning(f"Text search failed for '{search_query}': {e}")
                    text_results = []

                for res in news_results + text_results:
                    url = res.get("url", res.get("href", "#"))

                    if not url or url == "#" or url in seen_urls:
                        continue

                    seen_urls.add(url)
                    res["_search_query"] = search_query
                    all_results.append(res)

                    if len(all_results) >= 8:
                        break

                if len(all_results) >= 8:
                    break

        if not all_results:
            logger.info("No search results found")
            return "No relevant web search results found for this query.", []

        context_block = "LIVE WEB SEARCH RESULTS:\n"
        sources = []

        for i, res in enumerate(all_results, 1):
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
        return context_block, sources

    except Exception as e:
        logger.exception(f"Unexpected error in RAG engine: {e}")
        return "Live web context unavailable due to search error.", []


def scrape_article(url):
    """
    Scrape article content from a URL.
    
    Args:
        url: URL to scrape
    
    Returns:
        tuple: (article_text: str or None, error_message: str or None)
            Returns (text, None) on success
            Returns (None, error_msg) on failure
    """
    logger.info(f"Scraper: Fetching URL - {url[:50]}...")

    try:
        url = validate_url_input(url)
    except ValidationError as e:
        error_msg = f"Blocked unsafe URL: {str(e)}"
        logger.warning(error_msg)
        return None, error_msg
    
    try:
        # HEADERS: Mimic browser to avoid blocking
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
        
        # FETCH: Request with timeout
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
        
        # Validate response
        if response.status_code != 200:
            error_msg = f"Failed to fetch URL. HTTP {response.status_code}"
            logger.warning(error_msg)
            return None, error_msg
        
        # PARSE: Extract text from HTML
        logger.debug("Parsing HTML content...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract paragraphs (main content)
        paragraphs = soup.find_all('p')
        
        if not paragraphs:
            # Fallback: try to get any text
            logger.debug("No <p> tags found, extracting all text")
            article_text = soup.get_text()
        else:
            article_text = " ".join([p.get_text() for p in paragraphs])
        
        # NORMALIZE: Clean whitespace
        article_text = re.sub(r'\s+', ' ', article_text).strip()
        
        # VALIDATE: Check minimum content length
        word_count = len(article_text.split())
        if word_count < config.SCRAPER_MIN_WORDS:
            error_msg = (
                f"Could not extract enough text from this URL. "
                f"Found {word_count} words, need {config.SCRAPER_MIN_WORDS}."
            )
            logger.warning(error_msg)
            return None, error_msg
        
        logger.info(f"Scraper: Successfully extracted {len(article_text)} characters ({word_count} words)")
        return article_text, None
    
    except requests.exceptions.Timeout:
        error_msg = f"Request timed out (>{config.SCRAPER_TIMEOUT}s)"
        logger.error(error_msg)
        return None, error_msg
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: {str(e)[:50]}"
        logger.error(error_msg)
        return None, error_msg
    
    except Exception as e:
        error_msg = f"Scraper error: {str(e)[:100]}"
        logger.error(f"Unexpected error while scraping {url}: {e}")
        return None, error_msg