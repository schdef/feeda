import re
import math
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from dateutil import parser

from feeda.models import (
    TopicTrendItem,
    ArticleHeadline,
    CategoryTrend,
    HotspotCategory,
    DailyTimelineItem,
    InterestTrendsResponse,
    ModelSummary,
    TermWeightItem,
    FeedAffinityItem,
    LearningEventItem,
    LearningInspectorResponse,
)
from feeda.services.feed_parser import decode_html_text
from feeda.services.interest_grouper import (
    classify_article_topic,
    TOPIC_CATALOG,
    TOPIC_TAXONOMY,
    ALL_TOPICS,
)
from feeda.services.ranker import (
    extract_terms,
    update_term_weights,
    update_feed_affinity,
    STOP_WORDS,
)
from feeda.services.ai_summary import (
    extract_entities,
    parse_story_signature,
    KNOWN_ENTITIES,
)

logger = logging.getLogger(__name__)

# Standard action weights matching ranker.py
ACTION_WEIGHTS: Dict[str, float] = {
    "save_to_board": 4.0,
    "star": 3.5,
    "open_website": 3.0,
    "click_through": 2.5,
    "open_article": 2.0,
    "vote_up": 2.0,
    "read_long": 1.5,
    "read": 1.5,
    "read_medium": 0.5,
    "skip": -0.2,
    "read_short": -0.5,
    "unstar": -1.0,
    "vote_down": -3.0,
}

# Display name normalizations for topics and entities
DISPLAY_NAMES: Dict[str, str] = {
    "openai": "OpenAI",
    "chatgpt": "ChatGPT",
    "gpt-4": "GPT-4",
    "gpt-4o": "GPT-4o",
    "gpt-5": "GPT-5",
    "sora": "Sora",
    "dall-e": "DALL-E",
    "o1": "OpenAI o1",
    "o3": "OpenAI o3",
    "anthropic": "Anthropic",
    "claude": "Claude",
    "nvidia": "NVIDIA",
    "cuda": "CUDA",
    "rtx": "RTX",
    "blackwell": "NVIDIA Blackwell",
    "hopper": "NVIDIA Hopper",
    "deepseek": "DeepSeek",
    "mistral": "Mistral AI",
    "perplexity": "Perplexity",
    "gemini": "Google Gemini",
    "deepmind": "Google DeepMind",
    "copilot": "GitHub Copilot",
    "llama": "Llama 3",
    "tesla": "Tesla",
    "cybertruck": "Cybertruck",
    "model 3": "Model 3",
    "model y": "Model Y",
    "rivian": "Rivian",
    "byd": "BYD",
    "waymo": "Waymo",
    "apple": "Apple",
    "iphone": "iPhone",
    "ipad": "iPad",
    "macbook": "MacBook",
    "vision pro": "Apple Vision Pro",
    "google": "Google",
    "android": "Android",
    "microsoft": "Microsoft",
    "meta": "Meta",
    "amazon": "Amazon",
    "aws": "AWS",
    "spacex": "SpaceX",
    "starlink": "Starlink",
    "falcon 9": "Falcon 9",
    "starship": "Starship",
    "nasa": "NASA",
    "cisa": "CISA",
    "fbi": "FBI",
    "sec": "SEC",
    "ftc": "FTC",
    "doj": "DOJ",
    "ai": "Agentic AI",
    "llm": "LLMs",
    "llms": "LLMs & Foundation Models",
    "rag": "RAG Systems",
    "agentic": "Agentic AI",
    "agents": "Autonomous Agents",
    "rust": "Rust Programming",
    "python": "Python",
    "typescript": "TypeScript",
    "linux": "Linux Kernel",
    "kubernetes": "Kubernetes",
    "docker": "Docker & Containers",
    "postgres": "PostgreSQL",
    "sqlite": "SQLite",
    "semiconductor": "Semiconductors",
    "semiconductors": "Semiconductors",
    "battery": "Battery Technology",
    "batteries": "Battery Technology",
    "supercharger": "Superchargers",
    "autonomous": "Autonomous Driving",
    "robotaxi": "Robotaxi Fleets",
    "zero-day": "Zero-Day CVEs",
    "malware": "Malware & Threats",
    "ransomware": "Ransomware Defenses",
    "encryption": "End-to-End Encryption",
    "quantum": "Quantum Computing",
    "fusion": "Fusion Energy",
    "james webb": "James Webb Telescope",
}


def parse_dt(val: Any) -> Optional[datetime]:
    """Safely parse various datetime formats into a timezone-aware UTC datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    try:
        dt = parser.parse(str(val))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def get_period_dates(period: str, end_dt: Optional[datetime] = None) -> Tuple[datetime, datetime, int]:
    """
    Returns (start_dt, end_dt, num_days) for a given period string ('7d', '14d', '30d', 'all').
    Default is '7d'.
    """
    period_lower = (period or "7d").lower().strip()
    end = end_dt or datetime.now(timezone.utc)

    if period_lower == "14d":
        num_days = 14
        start = end - timedelta(days=14)
    elif period_lower == "30d":
        num_days = 30
        start = end - timedelta(days=30)
    elif period_lower == "all":
        num_days = 30
        start = end - timedelta(days=90)
    else:  # '7d' or fallback
        num_days = 7
        start = end - timedelta(days=7)

    return start, end, num_days


def format_topic_name(raw_name: str) -> str:
    """Formats topic entity/keyword into a human-readable title."""
    cleaned = raw_name.strip().lower()
    if cleaned in DISPLAY_NAMES:
        return DISPLAY_NAMES[cleaned]
    if len(cleaned) <= 4:
        return cleaned.upper()
    return cleaned.title()


def extract_category_hot_topics(
    articles: List[Dict[str, Any]],
    cat_slug: str,
    limit: int = 5,
) -> List[TopicTrendItem]:
    """
    Extracts and ranks the top distinct hot topics/entities for a category
    based on story signatures, extracted entities, and clean terms.
    """
    topic_stats: Dict[str, Dict[str, Any]] = {}

    for art in articles:
        title = art.get("title") or ""
        summary = art.get("summary") or ""
        dwell = float(art.get("dwell_time") or art.get("dwell_time_seconds") or 45.0)
        score = float(art.get("interest_score") or 0.0)

        # 1. Signature parts
        sig = art.get("story_signature") or ""
        parsed_sig = parse_story_signature(sig)
        sig_entities = set(parsed_sig.get("entities", []))
        sig_keys = set(parsed_sig.get("keys", []))

        # 2. Extracted entities & terms
        extracted_ents = set(extract_entities(f"{title} {summary}"))
        terms = set(extract_terms(title))

        all_candidates = set()
        # High value candidates
        for ent in sig_entities.union(extracted_ents):
            if ent and len(ent) >= 2:
                all_candidates.add((ent, 2.5))
        for k in sig_keys:
            if k and len(k) >= 3 and k not in STOP_WORDS:
                all_candidates.add((k, 2.0))
        for t in terms:
            if t and len(t) >= 4 and t not in STOP_WORDS:
                all_candidates.add((t, 1.0))

        for cand_raw, weight in all_candidates:
            cand_norm = cand_raw.lower()
            if cand_norm not in topic_stats:
                topic_stats[cand_norm] = {
                    "raw": cand_raw,
                    "count": 0,
                    "total_dwell": 0.0,
                    "weight_sum": 0.0,
                    "score_sum": 0.0,
                }
            topic_stats[cand_norm]["count"] += 1
            topic_stats[cand_norm]["total_dwell"] += dwell
            topic_stats[cand_norm]["weight_sum"] += weight
            topic_stats[cand_norm]["score_sum"] += score

    # Rank candidate topics
    ranked_candidates = []
    for cand_norm, stats in topic_stats.items():
        count = stats["count"]
        avg_dwell = stats["total_dwell"] / max(1, count)
        avg_score = stats["score_sum"] / max(1, count)
        weight_factor = stats["weight_sum"] / max(1, count)
        composite_score = round(
            (count * 1.5 * weight_factor) + (avg_dwell / 25.0) + max(0.0, avg_score),
            1,
        )
        ranked_candidates.append(
            TopicTrendItem(
                name=format_topic_name(stats["raw"]),
                count=count,
                avg_dwell=round(avg_dwell, 1),
                score=composite_score,
            )
        )

    # Sort descending by composite score, then count
    ranked_candidates.sort(key=lambda t: (t.score, t.count), reverse=True)

    # Pick unique formatted names
    unique_topics: List[TopicTrendItem] = []
    seen_names = set()
    for item in ranked_candidates:
        if item.name not in seen_names:
            seen_names.add(item.name)
            unique_topics.append(item)
        if len(unique_topics) >= limit:
            break

    # If category has fewer than limit, fill with default curated taxonomy entities
    if len(unique_topics) < limit and cat_slug in TOPIC_CATALOG:
        cat_def = TOPIC_CATALOG[cat_slug]
        fallback_candidates = list(cat_def.get("entities", [])) + list(cat_def.get("keywords", []))
        for fb in fallback_candidates:
            fb_name = format_topic_name(fb)
            if fb_name not in seen_names:
                seen_names.add(fb_name)
                unique_topics.append(
                    TopicTrendItem(
                        name=fb_name,
                        count=max(1, len(articles) // 2 or 1),
                        avg_dwell=42.0,
                        score=round(4.5 + len(unique_topics) * 0.5, 1),
                    )
                )
            if len(unique_topics) >= limit:
                break

    return unique_topics[:limit]


def sort_article_key(a: Dict[str, Any]):
    """Sort key for articles: highest interest_score first, then newest published_at/fetched_at."""
    score = float(a.get("interest_score") or 0.0)
    dt = parse_dt(a.get("published_at")) or parse_dt(a.get("fetched_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return (score, dt)


def to_article_headline(a: Dict[str, Any]) -> ArticleHeadline:
    """Converts an article row/dict to an ArticleHeadline response model."""
    pub_dt = parse_dt(a.get("published_at"))
    pub_str = pub_dt.isoformat() if pub_dt else (str(a["published_at"]) if a.get("published_at") else None)
    feed_title = decode_html_text(a.get("feed_title")) if a.get("feed_title") else None
    return ArticleHeadline(
        id=int(a["id"]),
        title=decode_html_text(a.get("title") or "Untitled"),
        feed_title=feed_title,
        url=str(a.get("url") or ""),
        published_at=pub_str,
        is_read=bool(a.get("is_read")),
        interest_score=round(float(a.get("interest_score") or 0.0), 2),
    )


def generate_demo_interest_trends(
    period: str,
    start_dt: datetime,
    end_dt: datetime,
    num_days: int,
) -> InterestTrendsResponse:
    """
    Generates realistic, rich demo analytics data when the database has 0 reads/interactions.
    Scales counts and trends proportionally to the selected time window.
    """
    multiplier = 1.0
    if period == "14d":
        multiplier = 1.9
    elif period == "30d":
        multiplier = 3.8
    elif period == "all":
        multiplier = 5.2

    # Timeline dates
    dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]

    # Demo category configurations
    demo_categories_spec = [
        {
            "name": "AI & Machine Learning",
            "slug": "ai-machine-learning",
            "emoji": "🤖",
            "base_articles": 48,
            "base_reads": 32,
            "base_dwell": 1920.0,
            "growth_pct": 54.2,
            "top_topics": [
                TopicTrendItem(name="Agentic AI", count=int(14 * multiplier), avg_dwell=84.0, score=9.4),
                TopicTrendItem(name="OpenAI o3", count=int(11 * multiplier), avg_dwell=62.0, score=8.7),
                TopicTrendItem(name="NVIDIA Blackwell", count=int(8 * multiplier), avg_dwell=45.0, score=7.9),
                TopicTrendItem(name="DeepSeek & Open Models", count=int(7 * multiplier), avg_dwell=40.0, score=7.1),
                TopicTrendItem(name="On-Device Inference", count=int(5 * multiplier), avg_dwell=35.0, score=6.5),
            ],
            "daily_pattern": [3, 4, 2, 6, 5, 5, 7],
            "source_feeds": ["OpenAI Blog", "MIT Technology Review", "ArXiv AI", "Hacker News"],
            "top_articles": [
                ArticleHeadline(
                    id=101,
                    title="OpenAI Unveils o3 Autonomous Reasoning Model with Benchmark Breakthroughs",
                    feed_title="OpenAI Blog",
                    url="https://openai.com/index/o3-preview",
                    published_at=(end_dt - timedelta(hours=6)).isoformat(),
                    is_read=True,
                    interest_score=9.8,
                ),
                ArticleHeadline(
                    id=102,
                    title="DeepSeek-V3 Architecture: Multi-Head Latent Attention in Production",
                    feed_title="Hacker News",
                    url="https://github.com/deepseek-ai/DeepSeek-V3",
                    published_at=(end_dt - timedelta(hours=18)).isoformat(),
                    is_read=False,
                    interest_score=9.3,
                ),
                ArticleHeadline(
                    id=103,
                    title="NVIDIA Blackwell B200 Systems Enter High-Volume Datacenter Deployments",
                    feed_title="MIT Technology Review",
                    url="https://technologyreview.com/2026/blackwell-datacenter",
                    published_at=(end_dt - timedelta(hours=30)).isoformat(),
                    is_read=True,
                    interest_score=8.9,
                ),
            ],
        },
        {
            "name": "Big Tech & Software",
            "slug": "big-tech-software",
            "emoji": "💻",
            "base_articles": 36,
            "base_reads": 22,
            "base_dwell": 1180.0,
            "growth_pct": 28.5,
            "top_topics": [
                TopicTrendItem(name="TypeScript 5.8", count=int(9 * multiplier), avg_dwell=55.0, score=8.1),
                TopicTrendItem(name="Rust in Linux Kernel", count=int(7 * multiplier), avg_dwell=50.0, score=7.4),
                TopicTrendItem(name="React 19 Actions", count=int(6 * multiplier), avg_dwell=42.0, score=6.8),
                TopicTrendItem(name="Docker & WebAssembly", count=int(4 * multiplier), avg_dwell=38.0, score=5.9),
                TopicTrendItem(name="PostgreSQL Vector Search", count=int(4 * multiplier), avg_dwell=36.0, score=5.7),
            ],
            "daily_pattern": [2, 3, 4, 3, 3, 4, 3],
            "source_feeds": ["The Verge", "InfoQ", "Ars Technica", "GitHub Blog"],
            "top_articles": [
                ArticleHeadline(
                    id=201,
                    title="TypeScript 5.8 Introduces Granular Type Checking and Node.js Modernization",
                    feed_title="InfoQ",
                    url="https://devblogs.microsoft.com/typescript/announcing-typescript-5-8/",
                    published_at=(end_dt - timedelta(hours=8)).isoformat(),
                    is_read=True,
                    interest_score=8.7,
                ),
                ArticleHeadline(
                    id=202,
                    title="Rust Mainline In-Kernel Drivers Deliver Zero Overhead in Linux 6.13",
                    feed_title="Ars Technica",
                    url="https://arstechnica.com/gadgets/2026/linux-kernel-rust-drivers/",
                    published_at=(end_dt - timedelta(hours=22)).isoformat(),
                    is_read=False,
                    interest_score=8.4,
                ),
                ArticleHeadline(
                    id=203,
                    title="PostgreSQL pgvector 0.8 Closes Performance Gap with Native Vector Databases",
                    feed_title="GitHub Blog",
                    url="https://github.blog/2026-postgres-vector-search",
                    published_at=(end_dt - timedelta(hours=40)).isoformat(),
                    is_read=False,
                    interest_score=7.9,
                ),
            ],
        },
        {
            "name": "Electric Vehicles & Mobility",
            "slug": "electric-vehicles-mobility",
            "emoji": "🚗",
            "base_articles": 24,
            "base_reads": 15,
            "base_dwell": 720.0,
            "growth_pct": 18.2,
            "top_topics": [
                TopicTrendItem(name="Tesla Robotaxi FSD", count=int(8 * multiplier), avg_dwell=48.0, score=7.5),
                TopicTrendItem(name="Solid-State Batteries", count=int(6 * multiplier), avg_dwell=44.0, score=6.9),
                TopicTrendItem(name="Rivian R2 Platform", count=int(5 * multiplier), avg_dwell=40.0, score=6.2),
                TopicTrendItem(name="BYD European Expansion", count=int(4 * multiplier), avg_dwell=34.0, score=5.4),
                TopicTrendItem(name="Megawatt Supercharging", count=int(3 * multiplier), avg_dwell=30.0, score=4.8),
            ],
            "daily_pattern": [2, 1, 3, 2, 2, 2, 3],
            "source_feeds": ["Electrek", "InsideEVs", "The Verge"],
            "top_articles": [
                ArticleHeadline(
                    id=301,
                    title="Tesla Robotaxi Commercial Testing Expands to Multi-City Trials in Austin",
                    feed_title="Electrek",
                    url="https://electrek.co/2026/tesla-robotaxi-expansion",
                    published_at=(end_dt - timedelta(hours=10)).isoformat(),
                    is_read=True,
                    interest_score=8.2,
                ),
                ArticleHeadline(
                    id=302,
                    title="Solid-State Battery Breakthrough Yields 800-Mile Range in Cold Weather Benchmarks",
                    feed_title="InsideEVs",
                    url="https://insideevs.com/news/solid-state-breakthrough-2026",
                    published_at=(end_dt - timedelta(hours=26)).isoformat(),
                    is_read=False,
                    interest_score=7.8,
                ),
                ArticleHeadline(
                    id=303,
                    title="Rivian R2 Pre-Production Prototypes Spotted Testing on Public Roads",
                    feed_title="The Verge",
                    url="https://theverge.com/transportation/rivian-r2-testing",
                    published_at=(end_dt - timedelta(hours=44)).isoformat(),
                    is_read=False,
                    interest_score=7.4,
                ),
            ],
        },
        {
            "name": "Cybersecurity & Privacy",
            "slug": "cybersecurity-privacy",
            "emoji": "🔒",
            "base_articles": 18,
            "base_reads": 12,
            "base_dwell": 580.0,
            "growth_pct": 32.1,
            "top_topics": [
                TopicTrendItem(name="Zero-Day CVEs", count=int(7 * multiplier), avg_dwell=52.0, score=7.2),
                TopicTrendItem(name="Passkeys & WebAuthn", count=int(5 * multiplier), avg_dwell=45.0, score=6.5),
                TopicTrendItem(name="Open Source Supply Chain", count=int(5 * multiplier), avg_dwell=41.0, score=6.1),
                TopicTrendItem(name="Post-Quantum Cryptography", count=int(4 * multiplier), avg_dwell=38.0, score=5.8),
                TopicTrendItem(name="E2E Encryption Audits", count=int(3 * multiplier), avg_dwell=32.0, score=5.0),
            ],
            "daily_pattern": [1, 2, 1, 2, 2, 2, 2],
            "source_feeds": ["BleepingComputer", "Krebs on Security", "Dark Reading"],
            "top_articles": [
                ArticleHeadline(
                    id=401,
                    title="Critical Zero-Day Vulnerability Discovered in Core Web Cryptography Stack",
                    feed_title="BleepingComputer",
                    url="https://bleepingcomputer.com/news/security/critical-cve-crypto-stack",
                    published_at=(end_dt - timedelta(hours=5)).isoformat(),
                    is_read=True,
                    interest_score=8.5,
                ),
                ArticleHeadline(
                    id=402,
                    title="Passkey Adoption Hits 75% Across Global Tier-1 Identity Providers",
                    feed_title="Krebs on Security",
                    url="https://krebsonsecurity.com/passkey-milestone-2026",
                    published_at=(end_dt - timedelta(hours=20)).isoformat(),
                    is_read=False,
                    interest_score=7.9,
                ),
                ArticleHeadline(
                    id=403,
                    title="Post-Quantum NIST Standard Enacted Across Federal Infrastructure",
                    feed_title="Dark Reading",
                    url="https://darkreading.com/vulnerabilities-threats/nist-pqc-mandate",
                    published_at=(end_dt - timedelta(hours=48)).isoformat(),
                    is_read=False,
                    interest_score=7.3,
                ),
            ],
        },
        {
            "name": "Science & Space",
            "slug": "science-space",
            "emoji": "🚀",
            "base_articles": 14,
            "base_reads": 9,
            "base_dwell": 410.0,
            "growth_pct": 12.4,
            "top_topics": [
                TopicTrendItem(name="Starship Flight 7", count=int(6 * multiplier), avg_dwell=46.0, score=6.7),
                TopicTrendItem(name="James Webb Exoplanets", count=int(5 * multiplier), avg_dwell=42.0, score=6.3),
                TopicTrendItem(name="Fusion Energy Milestones", count=int(4 * multiplier), avg_dwell=38.0, score=5.6),
                TopicTrendItem(name="Quantum Supremacy Logic", count=int(3 * multiplier), avg_dwell=35.0, score=5.2),
                TopicTrendItem(name="CRISPR Epigenetics", count=int(3 * multiplier), avg_dwell=31.0, score=4.9),
            ],
            "daily_pattern": [1, 1, 1, 2, 1, 1, 2],
            "source_feeds": ["SpaceNews", "Nature", "NASA Breaking News"],
            "top_articles": [
                ArticleHeadline(
                    id=501,
                    title="Starship Super Heavy Flight 7 Achieves Full Precision Tower Catch",
                    feed_title="SpaceNews",
                    url="https://spacenews.com/starship-flight-7-catch-success",
                    published_at=(end_dt - timedelta(hours=12)).isoformat(),
                    is_read=True,
                    interest_score=8.0,
                ),
                ArticleHeadline(
                    id=502,
                    title="James Webb Telescope Detects Atmospheric Water Vapor on Habitable-Zone Exoplanet",
                    feed_title="NASA Breaking News",
                    url="https://nasa.gov/mission_pages/webb/exoplanet-atmosphere-water",
                    published_at=(end_dt - timedelta(hours=32)).isoformat(),
                    is_read=False,
                    interest_score=7.6,
                ),
                ArticleHeadline(
                    id=503,
                    title="Magnetically Confined Fusion Experiment Generates Net Energy Gain in Sustained Pulse",
                    feed_title="Nature",
                    url="https://nature.com/articles/fusion-energy-gain-pulse",
                    published_at=(end_dt - timedelta(hours=50)).isoformat(),
                    is_read=False,
                    interest_score=7.2,
                ),
            ],
        },
        {
            "name": "Business & Markets",
            "slug": "business-markets",
            "emoji": "📈",
            "base_articles": 12,
            "base_reads": 7,
            "base_dwell": 310.0,
            "growth_pct": 8.7,
            "top_topics": [
                TopicTrendItem(name="Tech IPO Pipeline", count=int(5 * multiplier), avg_dwell=38.0, score=5.9),
                TopicTrendItem(name="Semiconductor Capex", count=int(4 * multiplier), avg_dwell=35.0, score=5.4),
                TopicTrendItem(name="Venture Capital AI Rounds", count=int(4 * multiplier), avg_dwell=32.0, score=5.1),
                TopicTrendItem(name="Central Bank Interest Rates", count=int(3 * multiplier), avg_dwell=28.0, score=4.5),
                TopicTrendItem(name="Cloud Infrastructure Margins", count=int(3 * multiplier), avg_dwell=26.0, score=4.2),
            ],
            "daily_pattern": [1, 1, 1, 1, 1, 1, 1],
            "source_feeds": ["Bloomberg Tech", "Financial Times", "Reuters"],
            "top_articles": [
                ArticleHeadline(
                    id=601,
                    title="Semiconductor Capex Surges Past $200B as Advanced Packaging Expands",
                    feed_title="Financial Times",
                    url="https://ft.com/content/semiconductor-capex-2026",
                    published_at=(end_dt - timedelta(hours=15)).isoformat(),
                    is_read=True,
                    interest_score=7.7,
                ),
                ArticleHeadline(
                    id=602,
                    title="Venture Capital Pours Record Funding into Autonomous Software Agents",
                    feed_title="Bloomberg Tech",
                    url="https://bloomberg.com/news/articles/2026-agentic-vc-funding",
                    published_at=(end_dt - timedelta(hours=35)).isoformat(),
                    is_read=False,
                    interest_score=7.1,
                ),
                ArticleHeadline(
                    id=603,
                    title="Cloud Hyperscalers Report Accelerated AI Infrastructure Operating Margins",
                    feed_title="Reuters",
                    url="https://reuters.com/technology/cloud-ai-margins-expansion",
                    published_at=(end_dt - timedelta(hours=52)).isoformat(),
                    is_read=False,
                    interest_score=6.8,
                ),
            ],
        },
    ]

    total_reads = sum(int(spec["base_reads"] * multiplier) for spec in demo_categories_spec)
    categories: List[CategoryTrend] = []

    # Map daily timeline
    daily_timeline: List[DailyTimelineItem] = []
    for day_idx, d_str in enumerate(dates):
        daily_timeline.append(DailyTimelineItem(date=d_str, total_reads=0, by_category={}))

    for spec in demo_categories_spec:
        art_count = int(spec["base_articles"] * multiplier)
        read_count = int(spec["base_reads"] * multiplier)
        dwell_secs = round(float(spec["base_dwell"] * multiplier), 1)
        share_pct = round((read_count / max(1, total_reads)) * 100.0, 1)

        # Generate day-by-day trend of length num_days
        base_pat = spec["daily_pattern"]
        daily_trend = []
        for i in range(num_days):
            pat_val = base_pat[i % len(base_pat)]
            daily_trend.append(max(1, int(pat_val * (multiplier / 1.5 if multiplier > 1 else 1.0))))
            daily_timeline[i].by_category[spec["slug"]] = daily_trend[i]
            daily_timeline[i].total_reads += daily_trend[i]

        cat_trend = CategoryTrend(
            name=spec["name"],
            slug=spec["slug"],
            emoji=spec["emoji"],
            article_count=art_count,
            read_count=read_count,
            total_dwell_seconds=dwell_secs,
            share_pct=share_pct,
            growth_pct=spec["growth_pct"],
            daily_trend=daily_trend,
            top_topics=spec["top_topics"],
            top_articles=spec.get("top_articles", []),
            source_feeds=spec.get("source_feeds", []),
        )
        categories.append(cat_trend)

    # Primary Hotspot is the top engagement category (AI & ML)
    hotspot_spec = demo_categories_spec[0]
    hotspot = HotspotCategory(
        name=hotspot_spec["name"],
        slug=hotspot_spec["slug"],
        emoji=hotspot_spec["emoji"],
        article_count=int(hotspot_spec["base_articles"] * multiplier),
        read_count=int(hotspot_spec["base_reads"] * multiplier),
        total_dwell_seconds=round(float(hotspot_spec["base_dwell"] * multiplier), 1),
        growth_pct=hotspot_spec["growth_pct"],
        top_topics=hotspot_spec["top_topics"],
        top_articles=hotspot_spec.get("top_articles", []),
        source_feeds=hotspot_spec.get("source_feeds", []),
    )

    demo_unread_catch_up = [
        ArticleHeadline(
            id=102,
            title="DeepSeek-V3 Architecture: Multi-Head Latent Attention in Production",
            feed_title="Hacker News",
            url="https://github.com/deepseek-ai/DeepSeek-V3",
            published_at=(end_dt - timedelta(hours=18)).isoformat(),
            is_read=False,
            interest_score=9.3,
        ),
        ArticleHeadline(
            id=202,
            title="Rust Mainline In-Kernel Drivers Deliver Zero Overhead in Linux 6.13",
            feed_title="Ars Technica",
            url="https://arstechnica.com/gadgets/2026/linux-kernel-rust-drivers/",
            published_at=(end_dt - timedelta(hours=22)).isoformat(),
            is_read=False,
            interest_score=8.4,
        ),
        ArticleHeadline(
            id=402,
            title="Passkey Adoption Hits 75% Across Global Tier-1 Identity Providers",
            feed_title="Krebs on Security",
            url="https://krebsonsecurity.com/passkey-milestone-2026",
            published_at=(end_dt - timedelta(hours=20)).isoformat(),
            is_read=False,
            interest_score=7.9,
        ),
        ArticleHeadline(
            id=203,
            title="PostgreSQL pgvector 0.8 Closes Performance Gap with Native Vector Databases",
            feed_title="GitHub Blog",
            url="https://github.blog/2026-postgres-vector-search",
            published_at=(end_dt - timedelta(hours=40)).isoformat(),
            is_read=False,
            interest_score=7.9,
        ),
        ArticleHeadline(
            id=302,
            title="Solid-State Battery Breakthrough Yields 800-Mile Range in Cold Weather Benchmarks",
            feed_title="InsideEVs",
            url="https://insideevs.com/news/solid-state-breakthrough-2026",
            published_at=(end_dt - timedelta(hours=26)).isoformat(),
            is_read=False,
            interest_score=7.8,
        ),
        ArticleHeadline(
            id=502,
            title="James Webb Telescope Detects Atmospheric Water Vapor on Habitable-Zone Exoplanet",
            feed_title="NASA Breaking News",
            url="https://nasa.gov/mission_pages/webb/exoplanet-atmosphere-water",
            published_at=(end_dt - timedelta(hours=32)).isoformat(),
            is_read=False,
            interest_score=7.6,
        ),
    ]

    return InterestTrendsResponse(
        period=period,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        is_demo=True,
        hotspot=hotspot,
        categories=categories,
        daily_timeline=daily_timeline,
        unread_catch_up=demo_unread_catch_up,
    )


async def get_interest_trends(db, period: str = "7d") -> InterestTrendsResponse:
    """
    Computes time-windowed interest trends and topic engagement.
    If database has 0 reads/interactions, seamlessly returns high quality demo data.
    """
    period_clean = (period or "7d").lower().strip()
    if period_clean not in ("7d", "14d", "30d", "all"):
        period_clean = "7d"

    start_dt, end_dt, num_days = get_period_dates(period_clean)

    # Check for reading activity
    interactions_count_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM interactions")
    read_articles_count_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM articles WHERE is_read = 1")

    total_interactions = interactions_count_row["cnt"] if interactions_count_row else 0
    total_read_articles = read_articles_count_row["cnt"] if read_articles_count_row else 0

    if total_interactions == 0 and total_read_articles == 0:
        # Fallback to realistic demo data
        return generate_demo_interest_trends(period_clean, start_dt, end_dt, num_days)

    # If period is 'all', compute actual earliest date
    if period_clean == "all":
        earliest_row = await db.fetch_one(
            "SELECT MIN(created_at) as min_dt FROM interactions"
        )
        earliest_dt = parse_dt(earliest_row["min_dt"]) if earliest_row else None
        if not earliest_dt:
            earliest_art = await db.fetch_one(
                "SELECT MIN(published_at) as min_pub, MIN(fetched_at) as min_fetch FROM articles"
            )
            earliest_dt = parse_dt(
                (earliest_art["min_pub"] if earliest_art else None)
                or (earliest_art["min_fetch"] if earliest_art else None)
            )
        if earliest_dt:
            start_dt = max(earliest_dt, end_dt - timedelta(days=90))
            num_days = max(7, min(60, (end_dt.date() - start_dt.date()).days + 1))
        else:
            num_days = 30
            start_dt = end_dt - timedelta(days=30)

    # Initialize daily timeline map
    dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]
    date_to_idx = {d: i for i, d in enumerate(dates)}
    daily_timeline_map: Dict[str, Dict[str, Any]] = {
        d: {"total_reads": 0, "by_category": {}} for d in dates
    }

    # Fetch all articles in DB with feed title and URL
    articles = await db.fetch_all("""
        SELECT a.id, a.feed_id, a.cluster_id, a.title, a.summary, a.url, a.published_at,
               a.fetched_at, a.is_read, a.read_at, a.interest_score, a.story_signature,
               f.title as feed_title
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
    """)

    # Fetch all interactions with article details
    interactions = await db.fetch_all("""
        SELECT i.id, i.article_id, i.action, i.dwell_time_seconds, i.created_at,
               a.title, a.summary, a.published_at, a.story_signature, a.interest_score, a.feed_id
        FROM interactions i
        JOIN articles a ON i.article_id = a.id
    """)

    # Group articles into topic categories
    cat_articles: Dict[str, List[Dict[str, Any]]] = {}
    art_category: Dict[int, str] = {}

    for art in articles:
        slug = classify_article_topic(art)
        if slug not in TOPIC_CATALOG:
            slug = "general-other"
        art_category[art["id"]] = slug
        if slug not in cat_articles:
            cat_articles[slug] = []
        cat_articles[slug].append(art)

    # Track category engagement metrics
    cat_reads: Dict[str, int] = {}
    cat_dwell: Dict[str, float] = {}
    cat_daily_trend: Dict[str, List[int]] = {slug: [0] * num_days for slug in TOPIC_CATALOG}

    # Set of processed reading events to avoid duplicates
    processed_events: Set[Tuple[int, str]] = set()

    for inter in interactions:
        inter_dt = parse_dt(inter["created_at"])
        if not inter_dt or inter_dt < start_dt or inter_dt > end_dt:
            continue

        art_id = inter["article_id"]
        slug = art_category.get(art_id, "general-other")
        date_str = inter_dt.strftime("%Y-%m-%d")
        event_key = (art_id, date_str)

        action = inter["action"]
        dwell = inter["dwell_time_seconds"]
        if dwell is None:
            dwell = 75.0 if action in ("read_long", "star", "save_to_board") else 45.0

        if event_key not in processed_events:
            processed_events.add(event_key)
            cat_reads[slug] = cat_reads.get(slug, 0) + 1
            if date_str in date_to_idx:
                d_idx = date_to_idx[date_str]
                cat_daily_trend[slug][d_idx] += 1
                daily_timeline_map[date_str]["total_reads"] += 1
                daily_timeline_map[date_str]["by_category"][slug] = (
                    daily_timeline_map[date_str]["by_category"].get(slug, 0) + 1
                )

        cat_dwell[slug] = cat_dwell.get(slug, 0.0) + float(dwell)

    # Also account for read articles without interaction rows
    for art in articles:
        if art.get("is_read"):
            read_dt = parse_dt(art.get("read_at") or art.get("fetched_at"))
            art_id = art["id"]
            slug = art_category.get(art_id, "general-other")
            date_str = read_dt.strftime("%Y-%m-%d") if read_dt else dates[-1]
            event_key = (art_id, date_str)

            if event_key not in processed_events:
                processed_events.add(event_key)
                cat_reads[slug] = cat_reads.get(slug, 0) + 1
                cat_dwell[slug] = cat_dwell.get(slug, 0.0) + 45.0
                if date_str in date_to_idx:
                    d_idx = date_to_idx[date_str]
                    cat_daily_trend[slug][d_idx] += 1
                    daily_timeline_map[date_str]["total_reads"] += 1
                    daily_timeline_map[date_str]["by_category"][slug] = (
                        daily_timeline_map[date_str]["by_category"].get(slug, 0) + 1
                    )

    total_reads_sum = sum(cat_reads.values())
    categories_result: List[CategoryTrend] = []

    # Assemble each category trend
    for slug, cat_def in TOPIC_CATALOG.items():
        arts = cat_articles.get(slug, [])
        reads = cat_reads.get(slug, 0)
        dwell_total = round(cat_dwell.get(slug, 0.0), 1)
        art_count = len(arts)

        if art_count == 0 and reads == 0:
            continue

        # Daily trend
        daily_trend = cat_daily_trend.get(slug, [0] * num_days)

        # Growth calculation: compare second half vs first half
        half = num_days // 2
        first_half = sum(daily_trend[:half])
        second_half = sum(daily_trend[half:])
        if first_half == 0 and second_half == 0:
            growth_pct = 0.0
        elif first_half == 0:
            growth_pct = round(second_half * 33.3, 1)
        else:
            growth_pct = round(((second_half - first_half) / first_half) * 100.0, 1)

        # Share percentage
        if total_reads_sum > 0:
            share_pct = round((reads / total_reads_sum) * 100.0, 1)
        else:
            total_arts_sum = max(1, len(articles))
            share_pct = round((art_count / total_arts_sum) * 100.0, 1)

        # Sort category articles by interest score desc, recency desc
        sorted_cat_arts = sorted(arts, key=sort_article_key, reverse=True)
        top_articles = [to_article_headline(a) for a in sorted_cat_arts[:3]]

        # Collect unique feed titles as source_feeds
        seen_feeds = set()
        source_feeds: List[str] = []
        for a in sorted_cat_arts:
            ft = decode_html_text(a.get("feed_title")) if a.get("feed_title") else None
            if ft and ft not in seen_feeds:
                seen_feeds.add(ft)
                source_feeds.append(ft)

        # Top 5 Hot Topics
        top_topics = extract_category_hot_topics(arts, slug, limit=5)

        categories_result.append(
            CategoryTrend(
                name=cat_def["name"],
                slug=slug,
                emoji=cat_def["emoji"],
                article_count=art_count,
                read_count=reads,
                total_dwell_seconds=dwell_total,
                share_pct=share_pct,
                growth_pct=growth_pct,
                daily_trend=daily_trend,
                top_topics=top_topics,
                top_articles=top_articles,
                source_feeds=source_feeds,
            )
        )

    # Sort categories by read count desc, then article count desc
    categories_result.sort(
        key=lambda c: (c.read_count * 2.0 + c.total_dwell_seconds / 60.0 + c.article_count),
        reverse=True,
    )

    # Determine Primary News Hotspot
    hotspot: Optional[HotspotCategory] = None
    if categories_result:
        top_cat = categories_result[0]
        hotspot = HotspotCategory(
            name=top_cat.name,
            slug=top_cat.slug,
            emoji=top_cat.emoji,
            article_count=top_cat.article_count,
            read_count=top_cat.read_count,
            total_dwell_seconds=top_cat.total_dwell_seconds,
            growth_pct=top_cat.growth_pct,
            top_topics=top_cat.top_topics,
            top_articles=top_cat.top_articles,
            source_feeds=top_cat.source_feeds,
        )

    # Build unread_catch_up: top 6 unread articles across highest-velocity categories
    velocity_ordered_cats = sorted(
        categories_result,
        key=lambda c: (c.growth_pct, c.read_count, c.article_count),
        reverse=True,
    )

    unread_candidates: List[Dict[str, Any]] = []
    seen_art_ids: Set[int] = set()

    for cat in velocity_ordered_cats:
        cat_arts = cat_articles.get(cat.slug, [])
        cat_unread = [
            a for a in cat_arts
            if not a.get("is_read") and a["id"] not in seen_art_ids
        ]
        cat_unread.sort(key=sort_article_key, reverse=True)
        for a in cat_unread:
            seen_art_ids.add(a["id"])
            unread_candidates.append(a)

    # If top velocity categories had fewer than 6, check any other unread articles
    if len(unread_candidates) < 6:
        other_unread = [
            a for a in articles
            if not a.get("is_read") and a["id"] not in seen_art_ids
        ]
        other_unread.sort(key=sort_article_key, reverse=True)
        for a in other_unread:
            seen_art_ids.add(a["id"])
            unread_candidates.append(a)

    unread_candidates.sort(key=sort_article_key, reverse=True)
    unread_catch_up = [to_article_headline(a) for a in unread_candidates[:6]]

    # Convert timeline map to list
    timeline_items = [
        DailyTimelineItem(
            date=d,
            total_reads=daily_timeline_map[d]["total_reads"],
            by_category=daily_timeline_map[d]["by_category"],
        )
        for d in dates
    ]

    return InterestTrendsResponse(
        period=period_clean,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        is_demo=False,
        hotspot=hotspot,
        categories=categories_result,
        daily_timeline=timeline_items,
        unread_catch_up=unread_catch_up,
    )


async def get_learning_inspector_data(db, limit: int = 30) -> LearningInspectorResponse:
    """
    Returns transparency data on how Feeda learned from user behavior:
    - Model summary & decay factor
    - Top positive & negative vocabulary terms
    - Feed affinities
    - Behavioral action weights
    - Recent learning event audit log
    """
    # 1. Check term_weights count
    summary_row = await db.fetch_one("""
        SELECT 
            COUNT(*) as total_learned_terms,
            SUM(CASE WHEN (positive_score - negative_score) > 0 THEN 1 ELSE 0 END) as positive_terms_count,
            SUM(CASE WHEN (negative_score - positive_score) > 0 THEN 1 ELSE 0 END) as negative_terms_count
        FROM term_weights
    """)

    total_terms = summary_row["total_learned_terms"] if summary_row and summary_row["total_learned_terms"] else 0
    pos_count = summary_row["positive_terms_count"] if summary_row and summary_row["positive_terms_count"] else 0
    neg_count = summary_row["negative_terms_count"] if summary_row and summary_row["negative_terms_count"] else 0

    # If 0 learned terms in DB, supply demo data with is_demo = True
    if total_terms == 0:
        return LearningInspectorResponse(
            model_summary=ModelSummary(
                total_learned_terms=1240,
                positive_terms_count=810,
                negative_terms_count=430,
                decay_factor=0.97,
            ),
            top_positive_terms=[
                TermWeightItem(term="agentic", positive_score=14.5, negative_score=0.3, net_score=14.2),
                TermWeightItem(term="neural", positive_score=12.0, negative_score=0.2, net_score=11.8),
                TermWeightItem(term="rust", positive_score=8.5, negative_score=0.1, net_score=8.4),
                TermWeightItem(term="benchmark", positive_score=7.2, negative_score=0.1, net_score=7.1),
                TermWeightItem(term="transformer", positive_score=6.8, negative_score=0.2, net_score=6.6),
                TermWeightItem(term="reasoning", positive_score=6.2, negative_score=0.1, net_score=6.1),
                TermWeightItem(term="multimodal", positive_score=5.7, negative_score=0.2, net_score=5.5),
                TermWeightItem(term="inference", positive_score=5.3, negative_score=0.1, net_score=5.2),
                TermWeightItem(term="deepseek", positive_score=5.0, negative_score=0.0, net_score=5.0),
                TermWeightItem(term="blackwell", positive_score=4.8, negative_score=0.0, net_score=4.8),
            ],
            top_negative_terms=[
                TermWeightItem(term="celebrity", positive_score=0.0, negative_score=8.5, net_score=-8.5),
                TermWeightItem(term="rumors", positive_score=0.2, negative_score=5.4, net_score=-5.2),
                TermWeightItem(term="clickbait", positive_score=0.1, negative_score=4.1, net_score=-4.0),
                TermWeightItem(term="gossip", positive_score=0.0, negative_score=3.6, net_score=-3.6),
                TermWeightItem(term="scandal", positive_score=0.2, negative_score=3.2, net_score=-3.0),
                TermWeightItem(term="tabloid", positive_score=0.0, negative_score=2.8, net_score=-2.8),
            ],
            feed_affinities=[
                FeedAffinityItem(feed_id=1, feed_title="Hacker News", articles_received=120, articles_read=68, affinity_score=0.89),
                FeedAffinityItem(feed_id=2, feed_title="The Netflix Tech Blog", articles_received=45, articles_read=25, affinity_score=0.82),
                FeedAffinityItem(feed_id=3, feed_title="InfoQ", articles_received=60, articles_read=30, affinity_score=0.74),
                FeedAffinityItem(feed_id=4, feed_title="SPIEGEL ONLINE", articles_received=90, articles_read=32, affinity_score=0.54),
            ],
            action_weights=ACTION_WEIGHTS,
            recent_events=[
                LearningEventItem(
                    id=1,
                    article_title="To Switch, or Not to Switch the AI Model",
                    action="open_article",
                    dwell_time_seconds=64.0,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    boosted_terms=["switch", "model", "ai"],
                ),
                LearningEventItem(
                    id=2,
                    article_title="DeepSeek-V3 Technical Report Released",
                    action="star",
                    dwell_time_seconds=92.0,
                    created_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                    boosted_terms=["deepseek", "technical", "report"],
                ),
                LearningEventItem(
                    id=3,
                    article_title="Rust for Linux Kernel Maintainers",
                    action="save_to_board",
                    dwell_time_seconds=140.0,
                    created_at=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                    boosted_terms=["rust", "linux", "kernel"],
                ),
            ],
            is_demo=True,
        )

    # Real data from database
    top_pos_rows = await db.fetch_all("""
        SELECT term, positive_score, negative_score, (positive_score - negative_score) as net_score
        FROM term_weights
        WHERE (positive_score - negative_score) > 0
        ORDER BY net_score DESC
        LIMIT ?
    """, (limit,))

    top_neg_rows = await db.fetch_all("""
        SELECT term, positive_score, negative_score, (positive_score - negative_score) as net_score
        FROM term_weights
        WHERE (negative_score - positive_score) > 0
        ORDER BY (negative_score - positive_score) DESC
        LIMIT ?
    """, (limit,))

    top_positive_terms = [
        TermWeightItem(
            term=r["term"],
            positive_score=round(float(r["positive_score"]), 2),
            negative_score=round(float(r["negative_score"]), 2),
            net_score=round(float(r["net_score"]), 2),
        )
        for r in top_pos_rows
    ]

    top_negative_terms = [
        TermWeightItem(
            term=r["term"],
            positive_score=round(float(r["positive_score"]), 2),
            negative_score=round(float(r["negative_score"]), 2),
            net_score=round(float(r["net_score"]), 2),
        )
        for r in top_neg_rows
    ]

    feed_affinity_rows = await db.fetch_all("""
        SELECT fa.feed_id, f.title as feed_title, fa.articles_received, fa.articles_read, fa.affinity_score
        FROM feed_affinity fa
        JOIN feeds f ON fa.feed_id = f.id
        ORDER BY fa.affinity_score DESC, fa.articles_read DESC
        LIMIT ?
    """, (limit,))

    feed_affinities = [
        FeedAffinityItem(
            feed_id=r["feed_id"],
            feed_title=r["feed_title"],
            articles_received=int(r["articles_received"]),
            articles_read=int(r["articles_read"]),
            affinity_score=round(float(r["affinity_score"]), 2),
        )
        for r in feed_affinity_rows
    ]

    recent_event_rows = await db.fetch_all("""
        SELECT i.id, i.article_id, i.action, i.dwell_time_seconds, i.created_at, a.title as article_title
        FROM interactions i
        JOIN articles a ON i.article_id = a.id
        ORDER BY i.created_at DESC, i.id DESC
        LIMIT 20
    """)

    recent_events = [
        LearningEventItem(
            id=r["id"],
            article_title=r["article_title"],
            action=r["action"],
            dwell_time_seconds=round(float(r["dwell_time_seconds"]), 1) if r["dwell_time_seconds"] is not None else None,
            created_at=str(r["created_at"]),
            boosted_terms=extract_terms(r["article_title"])[:5],
        )
        for r in recent_event_rows
    ]

    return LearningInspectorResponse(
        model_summary=ModelSummary(
            total_learned_terms=total_terms,
            positive_terms_count=pos_count,
            negative_terms_count=neg_count,
            decay_factor=0.97,
        ),
        top_positive_terms=top_positive_terms,
        top_negative_terms=top_negative_terms,
        feed_affinities=feed_affinities,
        action_weights=ACTION_WEIGHTS,
        recent_events=recent_events,
        is_demo=False,
    )


async def seed_demo_reading_activity(db) -> Dict[str, Any]:
    """
    Inserts sample articles and reading interactions to demonstrate live ML learning.
    Updates interactions, term_weights, and feed_affinity.
    """
    # 1. Ensure at least one feed exists
    feed_row = await db.fetch_one("SELECT id FROM feeds LIMIT 1")
    if feed_row:
        feed_id = feed_row["id"]
    else:
        feed_id = await db.execute("""
            INSERT INTO feeds (title, url, site_url, poll_interval_minutes)
            VALUES ('Feeda Tech Frontier', 'https://demo.feeda.dev/rss.xml', 'https://demo.feeda.dev', 30)
        """)

    # 2. Sample articles to seed
    sample_articles = [
        (
            "OpenAI Unveils o3 Autonomous Reasoning Model with Breakthrough Benchmarks",
            "OpenAI announced o3, its frontier reasoning model featuring agentic planning, mathematical proofs, and code synthesis surpassing human benchmarks.",
            "entity:openai,o3|cluster:product_launch_release|action:launch,announce|keys:reasoning,agentic,benchmark",
            [("open_article", 65.0), ("read_long", 115.0), ("star", None), ("save_to_board", None)],
        ),
        (
            "DeepSeek-V3 Open Architecture Challenges Proprietary Frontier Models",
            "DeepSeek released its V3 open-weights architecture with innovative Multi-Head Latent Attention and extreme inference efficiency.",
            "entity:deepseek|cluster:product_launch_release|action:release,unveil|keys:architecture,efficiency,inference",
            [("open_article", 75.0), ("vote_up", None)],
        ),
        (
            "NVIDIA Blackwell B200 GPUs Enter Volume Production to Meet Datacenter Demand",
            "Jensen Huang confirmed the Blackwell B200 AI accelerator production ramp, powering next-generation AI clusters globally.",
            "entity:nvidia,blackwell|cluster:product_launch_release|action:ship,roll_out|keys:accelerator,datacenter,production",
            [("open_website", 45.0), ("read_medium", 50.0)],
        ),
        (
            "Tesla Robotaxi Autonomous Trial Expands to New Metro Areas",
            "Tesla autonomous driving software v13 begins commercial driverless testing across Austin and the Bay Area.",
            "entity:tesla,robotaxi|cluster:product_launch_release|action:roll_out|keys:autonomous,driverless,fleet",
            [("read", 60.0)],
        ),
        (
            "Rust Language Integration Expands in Linux Kernel 6.13 Drivers",
            "The Linux kernel mainline merged expanded Rust abstractions for networking and storage device drivers.",
            "entity:linux|cluster:product_launch_release|action:debut|keys:rust,drivers,kernel",
            [("star", None)],
        ),
        (
            "Sensational Celebrity Rumors and Gossip Debunked Across Social Media",
            "Tabloid rumors and unverified gossip circulated online, widely criticized by media watchdogs as low-quality clickbait.",
            "entity:tiktok|cluster:legal_regulatory|action:investigate|keys:rumors,gossip,clickbait",
            [("vote_down", None), ("skip", 2.0)],
        ),
    ]

    seeded_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, (title, summary, sig, actions) in enumerate(sample_articles):
        # Insert article if not existing
        existing = await db.fetch_one("SELECT id FROM articles WHERE title = ?", (title,))
        if existing:
            art_id = existing["id"]
        else:
            url_hash = f"demo_hash_{idx}_{int(datetime.now().timestamp())}"
            art_id = await db.execute("""
                INSERT INTO articles (
                    feed_id, url, url_hash, title, summary,
                    published_at, fetched_at, is_read, read_at,
                    interest_score, story_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 5.0, ?)
            """, (
                feed_id,
                f"https://demo.feeda.dev/articles/{idx}",
                url_hash,
                title,
                summary,
                now_iso,
                now_iso,
                now_iso,
                sig,
            ))

        # Log interactions and update ML weights
        for action, dwell in actions:
            await db.execute("""
                INSERT INTO interactions (article_id, action, dwell_time_seconds, created_at)
                VALUES (?, ?, ?, ?)
            """, (art_id, action, dwell, now_iso))
            await update_term_weights(art_id, action, db)
            await update_feed_affinity(feed_id, action, db)

        seeded_count += 1

    # Also seed unread articles with high interest score for live catch-up
    unread_sample_articles = [
        (
            "Anthropic Unveils Claude 3.7 Sonnet Hybrid Architecture",
            "Anthropic introduced Claude 3.7 Sonnet, combining instant response generation with extended thinking capabilities.",
            "entity:anthropic,claude|cluster:product_launch_release|action:launch,introduce|keys:reasoning,code,sonnet",
            8.9,
        ),
        (
            "Solid-State Battery Prototype Enters Vehicle Integration with 900Wh/L Density",
            "Automotive battery engineers completed the first pack-level integration test of solid-state pouch cells yielding unprecedented range.",
            "entity:tesla,battery|cluster:product_launch_release|action:debut|keys:battery,energy,automotive",
            8.3,
        ),
        (
            "PostgreSQL pgvector 0.8 Closes Performance Gap with Native Vector Databases",
            "The pgvector extension merged HNSW indexing optimizations that reduce memory footprint by 40% and double query throughput.",
            "entity:postgres|cluster:product_launch_release|action:ship|keys:postgres,vector,database",
            7.9,
        ),
    ]

    for idx, (title, summary, sig, score) in enumerate(unread_sample_articles, start=len(sample_articles)):
        existing = await db.fetch_one("SELECT id FROM articles WHERE title = ?", (title,))
        if not existing:
            url_hash = f"demo_unread_hash_{idx}_{int(datetime.now().timestamp())}"
            await db.execute("""
                INSERT INTO articles (
                    feed_id, url, url_hash, title, summary,
                    published_at, fetched_at, is_read, read_at,
                    interest_score, story_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
            """, (
                feed_id,
                f"https://demo.feeda.dev/articles/{idx}",
                url_hash,
                title,
                summary,
                now_iso,
                now_iso,
                score,
                sig,
            ))
            seeded_count += 1

    return {
        "status": "ok",
        "message": "Demo interactions seeded",
        "articles_seeded": seeded_count,
    }
