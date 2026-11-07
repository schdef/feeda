import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from ..database import db

logger = logging.getLogger(__name__)

STOP_TERMS = {
    'http', 'https', 'www', 'com', 'org', 'net', 'html', 'item', 'url',
    'article', 'comments', 'points', 'feed', 'rss', 'xml', 'title', 'link',
    'and', 'the', 'for', 'with', 'from', 'about', 'von', 'und', 'die', 'der', 'das'
}

CURATED_FALLBACK_FEEDS: List[Dict[str, Any]] = [
    {
        "title": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "site_url": "https://news.ycombinator.com",
        "description": "Hacker News frontpage feeds",
        "favicon_url": "https://news.ycombinator.com/favicon.ico",
        "subscribers": 75000,
    },
    {
        "title": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "site_url": "https://www.theverge.com",
        "description": "Technology, science, art, and culture from The Verge",
        "favicon_url": "https://www.theverge.com/favicon.ico",
        "subscribers": 60000,
    },
    {
        "title": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "site_url": "https://techcrunch.com",
        "description": "Startup and Technology News",
        "favicon_url": "https://techcrunch.com/favicon.ico",
        "subscribers": 55000,
    },
    {
        "title": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "site_url": "https://arstechnica.com",
        "description": "Serving the Technologist for more than a decade. IT news, reviews, and analysis.",
        "favicon_url": "https://arstechnica.com/favicon.ico",
        "subscribers": 45000,
    },
    {
        "title": "SPIEGEL ONLINE - Schlagzeilen",
        "url": "https://www.spiegel.de/schlagzeilen/tops/index.rss",
        "site_url": "https://www.spiegel.de",
        "description": "Deutschlands führende Nachrichtenseite. Alles Wichtige aus Politik, Wirtschaft, Sport und Kultur.",
        "favicon_url": "https://www.spiegel.de/favicon.ico",
        "subscribers": 40000,
    },
    {
        "title": "MIT Technology Review",
        "url": "http://www.technologyreview.com/rss/rss.aspx",
        "site_url": "https://www.technologyreview.com",
        "description": "Our in-depth reporting on innovation reveals and explains what's really happening now.",
        "favicon_url": "https://www.technologyreview.com/favicon.ico",
        "subscribers": 38000,
    },
    {
        "title": "ScienceDaily",
        "url": "http://www.sciencedaily.com/newsfeed.xml",
        "site_url": "https://www.sciencedaily.com",
        "description": "Breaking science news and articles on global warming, extrasolar planets, stem cells, bird flu, autism, nanotechnology, dinosaurs, evolution.",
        "favicon_url": "https://www.sciencedaily.com/favicon.ico",
        "subscribers": 35000,
    },
    {
        "title": "Nature",
        "url": "https://www.nature.com/nature.rss",
        "site_url": "https://www.nature.com",
        "description": "Nature is the world's leading multidisciplinary science journal.",
        "favicon_url": "https://www.nature.com/favicon.ico",
        "subscribers": 30000,
    },
    {
        "title": "Tagesschau",
        "url": "https://www.tagesschau.de/xml/rss2/",
        "site_url": "https://www.tagesschau.de",
        "description": "Die aktuellen Beiträge der tagesschau",
        "favicon_url": "https://www.tagesschau.de/favicon.ico",
        "subscribers": 25000,
    },
    {
        "title": "BBC News - Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "site_url": "https://www.bbc.com/news/technology",
        "description": "The latest BBC News Technology stories",
        "favicon_url": "https://www.bbc.com/favicon.ico",
        "subscribers": 28000,
    }
]


GENERIC_DOMAINS = {
    "feedburner.com", "rss.feedspot.com", "cloud.feedly.com",
    "wordpress.com", "blogspot.com", "substack.com", "medium.com",
    "github.com", "youtube.com"
}


def clean_feed_id(feed_id: Optional[str]) -> str:
    """Strips leading 'feed/' or 'feed:' from feedly feedId."""
    if not feed_id:
        return ""
    return re.sub(r"^feed[:/]+", "", feed_id.strip())


def normalize_feed_url(url: Optional[str]) -> str:
    """
    Robust normalization for feed URLs:
    - Lowercase
    - Strip whitespace
    - Strip leading 'feed/' or 'feed:' prefix
    - Strip 'http://' or 'https://'
    - Strip optional leading 'www.'
    - Strip query parameters ('?') and fragments ('#')
    - Strip trailing slashes
    """
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^feed[:/]+", "", u)
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("?")[0].split("#")[0]
    return u.rstrip("/")


def extract_domain(url: Optional[str]) -> str:
    if not url:
        return ""
    u = url.strip().lower()
    u = re.sub(r"^feed[:/]+", "", u)
    if "://" not in u:
        u = "http://" + u
    try:
        dom = urlparse(u).netloc.lower()
        if dom.startswith("www."):
            dom = dom[4:]
        return dom
    except Exception:
        return ""


def normalize_title(title: Optional[str]) -> str:
    if not title:
        return ""
    t = title.strip().lower()
    t = re.sub(r"\s*[-–—|]\s*(all posts|rss|feed|frontpage|aktuell|schlagzeilen|news).*$", "", t)
    return re.sub(r"[^a-z0-9]", "", t)


def is_subscribed_feed(
    feed_url: Optional[str],
    site_url: Optional[str],
    title: Optional[str],
    subscribed_urls: set,
    subscribed_domains: set,
    subscribed_titles: set
) -> bool:
    """Checks if a candidate feed matches any user subscription via URL, domain, or title."""
    if feed_url:
        norm_u = normalize_feed_url(feed_url)
        if norm_u and norm_u in subscribed_urls:
            return True
        dom_u = extract_domain(feed_url)
        if dom_u and dom_u not in GENERIC_DOMAINS and dom_u in subscribed_domains:
            return True

    if site_url:
        norm_su = normalize_feed_url(site_url)
        if norm_su and norm_su in subscribed_urls:
            return True
        dom_s = extract_domain(site_url)
        if dom_s and dom_s not in GENERIC_DOMAINS and dom_s in subscribed_domains:
            return True

    if title:
        norm_t = normalize_title(title)
        if len(norm_t) >= 4 and norm_t in subscribed_titles:
            return True

    return False


async def get_user_subscription_sets() -> tuple[set, set, set]:
    """Fetches user subscriptions and builds sets of normalized URLs, domains, and titles."""
    user_rows = await db.fetch_all("SELECT url, site_url, title FROM feeds")
    subscribed_urls = set()
    subscribed_domains = set()
    subscribed_titles = set()

    for r in user_rows:
        u = r.get("url")
        if u:
            norm_u = normalize_feed_url(u)
            if norm_u:
                subscribed_urls.add(norm_u)
            dom_u = extract_domain(u)
            if dom_u and dom_u not in GENERIC_DOMAINS:
                subscribed_domains.add(dom_u)
        su = r.get("site_url")
        if su:
            norm_su = normalize_feed_url(su)
            if norm_su:
                subscribed_urls.add(norm_su)
            dom_s = extract_domain(su)
            if dom_s and dom_s not in GENERIC_DOMAINS:
                subscribed_domains.add(dom_s)
        t = r.get("title")
        if t:
            norm_t = normalize_title(t)
            if len(norm_t) >= 4:
                subscribed_titles.add(norm_t)

    return subscribed_urls, subscribed_domains, subscribed_titles


def parse_feedly_item(item: Dict[str, Any]) -> Dict[str, Any]:
    feed_id = item.get("feedId") or item.get("id") or ""
    url = clean_feed_id(feed_id)
    site_url = item.get("website")
    favicon_url = item.get("iconUrl") or item.get("visualUrl")
    if not favicon_url and site_url:
        try:
            domain = urlparse(site_url).netloc
            if domain:
                favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        except Exception:
            pass

    return {
        "title": item.get("title") or (url if url else "Untitled Feed"),
        "url": url,
        "site_url": site_url,
        "description": item.get("description"),
        "favicon_url": favicon_url,
        "subscribers": int(item.get("subscribers") or 0),
        "is_subscribed": False,
    }


async def search_feedly(query: str, count: int = 20) -> List[Dict[str, Any]]:
    """Query Feedly's search API with a 5s timeout."""
    if not query or not query.strip():
        return []

    url = "https://cloud.feedly.com/v3/search/feeds"
    params = {"query": query.strip(), "count": count}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                parsed = []
                for item in results:
                    entry = parse_feedly_item(item)
                    if entry["url"]:
                        parsed.append(entry)
                return parsed
            else:
                logger.warning(f"Feedly search returned status {resp.status_code} for query: {query}")
                return []
    except Exception as e:
        logger.warning(f"Feedly search request failed: {e}")
        return []


async def search_feeds(query: str, count: int = 20) -> List[Dict[str, Any]]:
    """
    Search feeds via Feedly with database subscription check
    and graceful fallback to local / curated feeds.
    """
    if not query or not query.strip():
        return []

    q = query.strip()

    # Get user's current subscriptions for is_subscribed checking
    subscribed_urls, subscribed_domains, subscribed_titles = await get_user_subscription_sets()

    # Try Feedly
    results = []
    try:
        results = await search_feedly(q, count=count)
    except Exception as e:
        logger.warning(f"Error fetching from Feedly, falling back: {e}")

    # Fallback if no external results
    if not results:
        # Search local feeds in DB
        pattern = f"%{q}%"
        db_rows = await db.fetch_all("""
            SELECT title, url, site_url, favicon_url, description
            FROM feeds
            WHERE title LIKE ? OR url LIKE ? OR description LIKE ?
            LIMIT ?
        """, (pattern, pattern, pattern, count))

        seen_urls = set()
        for r in db_rows:
            norm = normalize_feed_url(r.get("url"))
            if norm and norm not in seen_urls:
                seen_urls.add(norm)
                results.append({
                    "title": r.get("title") or "Untitled Feed",
                    "url": r.get("url") or "",
                    "site_url": r.get("site_url"),
                    "description": r.get("description"),
                    "favicon_url": r.get("favicon_url"),
                    "subscribers": 0,
                    "is_subscribed": True,
                })

        # Also search curated fallback feeds
        q_lower = q.lower()
        for c in CURATED_FALLBACK_FEEDS:
            norm = normalize_feed_url(c["url"])
            if norm in seen_urls:
                continue
            if (
                q_lower in c["title"].lower()
                or (c.get("description") and q_lower in c["description"].lower())
                or (c.get("site_url") and q_lower in c["site_url"].lower())
            ):
                seen_urls.add(norm)
                item = dict(c)
                item["is_subscribed"] = is_subscribed_feed(
                    item.get("url"), item.get("site_url"), item.get("title"),
                    subscribed_urls, subscribed_domains, subscribed_titles
                )
                results.append(item)

        # If still empty, return top curated feeds as a discovery fallback
        if not results:
            for c in CURATED_FALLBACK_FEEDS[:count]:
                norm = normalize_feed_url(c["url"])
                item = dict(c)
                item["is_subscribed"] = is_subscribed_feed(
                    item.get("url"), item.get("site_url"), item.get("title"),
                    subscribed_urls, subscribed_domains, subscribed_titles
                )
                results.append(item)

    # Mark is_subscribed
    for item in results:
        item["is_subscribed"] = is_subscribed_feed(
            item.get("url"), item.get("site_url"), item.get("title"),
            subscribed_urls, subscribed_domains, subscribed_titles
        )

    return results[:count]


async def get_feed_suggestions(refresh: Optional[int] = 0) -> Dict[str, Any]:
    """
    Generate personalized feed suggestions based on learned term weights and feed affinity.
    Supports deterministic / diverse refresh via the refresh param.
    """
    # 1. Query term_weights
    term_rows = await db.fetch_all("""
        SELECT term, positive_score 
        FROM term_weights 
        WHERE positive_score > 0 
        ORDER BY positive_score DESC 
        LIMIT 25
    """)

    # 2. Query top feed affinity
    affinity_rows = await db.fetch_all("""
        SELECT f.title 
        FROM feed_affinity fa 
        JOIN feeds f ON fa.feed_id = f.id 
        WHERE fa.affinity_score > 0.5 
        LIMIT 5
    """)

    # Collect candidate terms
    candidates = []
    for r in term_rows:
        t = (r.get("term") or "").strip().lower()
        if len(t) > 2 and t not in STOP_TERMS and not t.isdigit():
            candidates.append(t)

    for r in affinity_rows:
        title = (r.get("title") or "").strip().lower()
        if title:
            candidates.append(title)

    # Deduplicate while preserving order
    candidates = list(dict.fromkeys(candidates))

    # RNG initialization
    rng = random.Random(refresh if refresh is not None else None)

    # Select 2-3 terms
    if candidates:
        if len(candidates) >= 3:
            k = 2 if (refresh is not None and refresh % 2 == 1) else 3
        else:
            k = len(candidates)
        sampled_terms = rng.sample(candidates, k=k)
    else:
        # Cold start: default high quality topics
        defaults = ["technology", "science", "nachrichten"]
        k = 2 if (refresh is not None and refresh % 2 == 1) else 3
        sampled_terms = rng.sample(defaults, k=min(len(defaults), k))

    # User's current subscriptions
    subscribed_urls, subscribed_domains, subscribed_titles = await get_user_subscription_sets()

    # Query external feeds for each sampled term concurrently
    search_tasks = [search_feedly(term, count=8) for term in sampled_terms]
    search_results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

    reason = f"Based on your interest in: {', '.join(sampled_terms)}"
    suggestions = []
    seen_urls = set()
    seen_titles = set()

    for term_res in search_results_list:
        if isinstance(term_res, Exception) or not term_res:
            continue
        for feed in term_res:
            norm = normalize_feed_url(feed.get("url"))
            norm_t = normalize_title(feed.get("title"))
            if not norm or norm in seen_urls:
                continue
            if norm_t and len(norm_t) >= 4 and norm_t in seen_titles:
                continue
            if is_subscribed_feed(
                feed.get("url"), feed.get("site_url"), feed.get("title"),
                subscribed_urls, subscribed_domains, subscribed_titles
            ):
                continue
            seen_urls.add(norm)
            if norm_t and len(norm_t) >= 4:
                seen_titles.add(norm_t)
            feed_dict = dict(feed)
            feed_dict["reason"] = reason
            feed_dict["is_subscribed"] = False
            suggestions.append(feed_dict)

    # Fallback to curated feeds if suggestions are sparse (e.g. offline or no results)
    if len(suggestions) < 3:
        for c in CURATED_FALLBACK_FEEDS:
            norm = normalize_feed_url(c["url"])
            norm_t = normalize_title(c.get("title"))
            if not norm or norm in seen_urls:
                continue
            if norm_t and len(norm_t) >= 4 and norm_t in seen_titles:
                continue
            if is_subscribed_feed(
                c.get("url"), c.get("site_url"), c.get("title"),
                subscribed_urls, subscribed_domains, subscribed_titles
            ):
                continue
            seen_urls.add(norm)
            if norm_t and len(norm_t) >= 4:
                seen_titles.add(norm_t)
            item = dict(c)
            item["reason"] = reason
            item["is_subscribed"] = False
            suggestions.append(item)
            if len(suggestions) >= 10:
                break

    return {
        "suggestions": suggestions[:20],
        "topics": sampled_terms
    }
