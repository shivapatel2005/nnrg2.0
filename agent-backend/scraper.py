"""
scraper.py
----------
Live website fetcher for the NNRG College website (https://nnrg.edu.in/).

Discovery strategy (tried in order, first one that yields results wins):
  1. DuckDuckGo HTML search scoped to the official domain
  2. Sitemap.xml
  3. BFS crawl from homepage (fallback)

No content is cached between requests — every call fetches fresh data.
"""

import os
import re
import logging
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("NNRG_BASE_URL", "https://nnrg.edu.in/")
DOMAIN = urlparse(BASE_URL).netloc
MAX_PAGES = int(os.getenv("MAX_PAGES_PER_QUERY", "6"))
MAX_CHARS_PER_DOC = int(os.getenv("MAX_CHARS_PER_DOC", "6000"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NNRG-Assistant/1.0; +https://nnrg.edu.in/)",
    "Accept-Language": "en-US,en;q=0.9",
}

STOPWORDS = {
    "the", "is", "are", "a", "an", "of", "for", "to", "in", "on", "and",
    "what", "when", "where", "who", "how", "does", "do", "i", "me",
    "please", "tell", "about", "can", "you", "list", "give", "details",
}

NOISE_TAGS = ["script", "style", "noscript", "header", "footer", "nav",
              "form", "iframe", "svg", "button"]
NOISE_CLASS_HINTS = [
    "nav", "navbar", "menu", "footer", "header", "sidebar", "breadcrumb",
    "advert", "ads", "cookie", "social", "share", "carousel-control",
]


# ─── Tokenization helpers ─────────────────────────────────────────────────────

def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _is_internal(url: str) -> bool:
    try:
        return urlparse(url).netloc in ("", DOMAIN)
    except Exception:
        return False


def _normalize(url: str) -> str:
    url = urljoin(BASE_URL, url)
    return url.split("#")[0].rstrip("/")


# ─── Fetching ─────────────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = 15):
    """Fetch a single URL. Returns (bytes, content_type) or (None, None)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.content, resp.headers.get("Content-Type", "")
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
    return None, None


# ─── Discovery strategies ─────────────────────────────────────────────────────

def _search_duckduckgo(query: str, max_results: int = 12) -> list:
    """Site-scoped DuckDuckGo search (HTML endpoint, no API key needed)."""
    try:
        resp = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": f"site:{DOMAIN} {query}"},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            if href and _is_internal(href):
                links.append(_normalize(href))
            if len(links) >= max_results:
                break
        return links
    except Exception as e:
        logger.warning("DuckDuckGo search failed: %s", e)
        return []


def _get_sitemap_links(max_results: int = 150) -> list:
    for path in ("sitemap.xml", "sitemap_index.xml"):
        content, _ = fetch_url(urljoin(BASE_URL, path))
        if not content:
            continue
        try:
            soup = BeautifulSoup(content, "xml")
            locs = [loc.text.strip() for loc in soup.find_all("loc")]
            if locs:
                return locs[:max_results]
        except Exception:
            continue
    return []


def _bfs_crawl(start_url: str, max_pages: int = 40, max_depth: int = 2) -> list:
    """Fallback BFS crawl when search and sitemap both fail."""
    visited, queue, discovered = set(), deque([(start_url, 0)]), []
    while queue and len(discovered) < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        content, ctype = fetch_url(url)
        if not content:
            continue
        discovered.append(url)
        if "text/html" not in (ctype or "").lower():
            continue
        try:
            soup = BeautifulSoup(content, "lxml")
            for a in soup.find_all("a", href=True):
                href = _normalize(a["href"])
                if _is_internal(href) and href not in visited:
                    queue.append((href, depth + 1))
        except Exception:
            continue
    return discovered


def _score_url(url: str, query_tokens: set) -> int:
    path_tokens = _tokenize(urlparse(url).path.replace("-", " ").replace("_", " "))
    return len(path_tokens & query_tokens)


# ─── Public API ───────────────────────────────────────────────────────────────

def discover_candidate_urls(query: str) -> list:
    """
    Returns a ranked list of candidate URLs (≤ MAX_PAGES) for the given query.
    Always fetches live — nothing is cached between calls.
    """
    query_tokens = _tokenize(query)

    links = _search_duckduckgo(query)
    if not links:
        links = _get_sitemap_links()
    if not links:
        links = _bfs_crawl(BASE_URL)
    if not links:
        return [BASE_URL]

    unique = list(dict.fromkeys(links + [BASE_URL]))
    ranked = sorted(unique, key=lambda u: -_score_url(u, query_tokens))
    logger.info("Discovered %d candidate URLs for query: %r", len(ranked[:MAX_PAGES]), query)
    return ranked[:MAX_PAGES]


def extract_html_text(html_bytes: bytes) -> str:
    """Extract clean readable text from HTML bytes."""
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for el in soup.find_all(True):
        classes = " ".join(el.get("class", [])).lower()
        tag_id = (el.get("id") or "").lower()
        if any(hint in classes + " " + tag_id for hint in NOISE_CLASS_HINTS):
            el.decompose()

    main = soup.find("main") or soup.find(id="content") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
    return "\n".join(lines)[:MAX_CHARS_PER_DOC]
