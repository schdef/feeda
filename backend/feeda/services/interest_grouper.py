import re
import logging
from typing import List, Dict, Any, Optional, Set

from feeda.services.ai_summary import (
    extract_entities,
    parse_story_signature,
    generate_story_signature,
    clean_html_text,
)
from feeda.services.feed_parser import decode_html_text
from feeda.routers.articles import compute_likelihood_tier, get_likelihood_thresholds

logger = logging.getLogger(__name__)

# Predefined Topic Taxonomy for Interest Board
TOPIC_TAXONOMY: List[Dict[str, Any]] = [
    {
        "name": "AI & Machine Learning",
        "emoji": "🤖",
        "slug": "ai-machine-learning",
        "entities": {
            "openai", "chatgpt", "gpt-4", "gpt-4o", "gpt-5", "sora", "dall-e", "o1", "o3",
            "anthropic", "claude", "nvidia", "cuda", "geforce", "rtx", "blackwell", "hopper",
            "deepseek", "mistral", "perplexity", "hugging face", "stability ai", "midjourney",
            "gemini", "deepmind", "copilot", "llama", "sam altman", "jensen huang"
        },
        "action_clusters": set(),
        "keywords": {
            "ai", "artificial intelligence", "machine learning", "deep learning", "neural network",
            "neural networks", "llm", "llms", "nlp", "transformer", "transformers", "diffusion",
            "genai", "generative ai", "prompt", "prompts", "prompting", "agentic", "agent",
            "agents", "agi", "superintelligence", "super intelligence", "multimodal", "multi-modal",
            "fine-tuning", "chatbot", "chatbots", "rag", "embeddings", "synthetic data",
            "context window", "tokenizer", "tokens", "inference", "ai boom", "ai models",
            "ai agent", "ai agents", "foundation model", "foundation models"
        }
    },
    {
        "name": "Electric Vehicles & Mobility",
        "emoji": "🚗",
        "slug": "electric-vehicles-mobility",
        "entities": {
            "tesla", "cybertruck", "model 3", "model y", "model s", "model x", "roadster",
            "supercharger", "rivian", "r1t", "r1s", "lucid", "byd", "ford", "gm", "general motors",
            "chevrolet", "volkswagen", "bmw", "mercedes", "audi", "porsche", "toyota", "honda",
            "hyundai", "kia", "waymo", "cruise", "zoox", "elon musk"
        },
        "action_clusters": {"recall_safety"},
        "keywords": {
            "ev", "evs", "electric vehicle", "electric vehicles", "electric car", "electric cars",
            "battery", "batteries", "charging", "supercharger", "autonomous vehicle",
            "autonomous driving", "self-driving", "driverless", "robotaxi", "robotaxis",
            "autopilot", "fsd", "full self-driving", "automotive", "car", "cars", "vehicle",
            "vehicles", "suv", "suvs", "sedan", "powertrain", "gigafactory", "lidar", "mobility",
            "automaker", "automakers"
        }
    },
    {
        "name": "Big Tech & Software",
        "emoji": "💻",
        "slug": "big-tech-software",
        "entities": {
            "apple", "iphone", "ipad", "macbook", "mac", "vision pro", "airpods", "apple watch",
            "ios", "macos", "google", "android", "pixel", "youtube", "chrome", "chromebook",
            "microsoft", "windows", "azure", "office 365", "meta", "facebook", "instagram",
            "threads", "whatsapp", "amazon", "aws", "alexa", "kindle", "prime", "github",
            "gitlab", "discord", "stripe", "paypal", "salesforce", "oracle", "tim cook",
            "satya nadella", "sundar pichai", "mark zuckerberg", "jeff bezos", "bill gates"
        },
        "action_clusters": set(),
        "keywords": {
            "software", "app", "apps", "browser", "operating system", "os", "linux", "kernel",
            "cloud", "saas", "api", "apis", "sdk", "sdks", "platform", "open source",
            "open-source", "oss", "developer", "developers", "programming", "programmer",
            "coding", "codebase", "python", "javascript", "typescript", "rust", "golang", "c++",
            "react", "vue", "database", "sqlite", "postgres", "postgresql", "redis", "docker",
            "kubernetes", "backend", "frontend", "compiler", "git", "framework",
            "web development", "firmware", "web"
        }
    },
    {
        "name": "Cybersecurity & Privacy",
        "emoji": "🔒",
        "slug": "cybersecurity-privacy",
        "entities": {
            "cisa", "fbi"
        },
        "action_clusters": {"security_incident"},
        "keywords": {
            "security", "cybersecurity", "cyberattack", "cyberattacks", "hack", "hacker", "hackers",
            "hacking", "hacked", "breach", "breached", "leak", "leaked", "leaks", "vulnerability",
            "vulnerabilities", "exploit", "exploits", "exploited", "zero-day", "zero-days", "flaw",
            "flaws", "malware", "ransomware", "spyware", "trojan", "phishing", "ddos", "botnet",
            "encryption", "encrypted", "privacy", "surveillance", "cve", "infosec", "passwords",
            "credential", "credentials", "backdoor", "spy", "espionage", "data breach", "patch",
            "security flaw"
        }
    },
    {
        "name": "Business & Markets",
        "emoji": "📈",
        "slug": "business-markets",
        "entities": {
            "sec", "federal reserve"
        },
        "action_clusters": {"business_deal", "workforce_leadership"},
        "keywords": {
            "business", "market", "markets", "stock", "stocks", "shares", "revenue", "earnings",
            "quarter", "q1", "q2", "q3", "q4", "investor", "investors", "investment",
            "investments", "invest", "invested", "valuation", "ipo", "funding", "fund",
            "fundraise", "round", "venture capital", "vc", "yc", "acquisition", "acquire",
            "acquired", "merger", "profit", "profits", "profitable", "loss", "losses", "economy",
            "economic", "inflation", "recession", "gdp", "trade", "tariffs", "tariff", "fed",
            "rate cut", "interest rates", "sales", "ceo", "cfo", "layoffs", "layoff", "job cuts",
            "startup", "startups", "wall street", "dow", "nasdaq", "s&p"
        }
    },
    {
        "name": "Science & Space",
        "emoji": "🚀",
        "slug": "science-space",
        "entities": {
            "spacex", "starlink", "falcon 9", "starship", "nasa", "esa", "blue origin"
        },
        "action_clusters": set(),
        "keywords": {
            "space", "orbit", "orbital", "satellite", "satellites", "rocket", "rockets", "launch",
            "moon", "mars", "astronomy", "telescope", "james webb", "hubble", "astrophysics",
            "physics", "quantum", "quantum computing", "biology", "biological", "genetics",
            "genome", "dna", "rna", "glp-1", "glp-1s", "glp1", "medical", "medicine",
            "healthcare", "disease", "disorder", "disorders", "cancer", "drug", "drugs",
            "vaccine", "clinical trial", "research", "researchers", "scientists", "laboratory",
            "fusion", "nuclear", "particle", "cosmos", "universe", "planet", "asteroid",
            "astronaut", "interspecies", "scientific"
        }
    },
    {
        "name": "Media & Entertainment",
        "emoji": "🎬",
        "slug": "media-entertainment",
        "entities": {
            "tiktok", "bytedance", "netflix", "spotify", "playstation", "nintendo", "sony"
        },
        "action_clusters": set(),
        "keywords": {
            "media", "streaming", "music", "album", "song", "video", "film", "films", "movie",
            "movies", "cinema", "tv", "television", "series", "episode", "episodes", "podcast",
            "podcasts", "creator", "creators", "influencer", "influencers", "hollywood",
            "entertainment", "game", "games", "gaming", "gamer", "console", "switch", "steam",
            "trailer", "box office", "anime", "comic", "books", "puzzle", "sony", "playstation",
            "ps5", "ps6"
        }
    },
    {
        "name": "Hardware & Gadgets",
        "emoji": "📱",
        "slug": "hardware-gadgets",
        "entities": {
            "intel", "amd", "qualcomm", "arm", "tsmc", "asml", "radeon", "ryzen", "snapdragon"
        },
        "action_clusters": set(),
        "keywords": {
            "hardware", "semiconductor", "semiconductors", "chip", "chips", "chipset", "silicon",
            "processor", "processors", "cpu", "gpu", "soc", "wafer", "transistor", "fab",
            "fabrication", "gadget", "gadgets", "smartphone", "smartphones", "phone", "tablet",
            "display", "oled", "amoled", "screen", "keyboard", "mouse", "sensor", "sensors",
            "wearable", "smartwatch", "headset", "vr headset", "ar glasses", "camera"
        }
    },
    {
        "name": "Energy & Climate",
        "emoji": "⚡",
        "slug": "energy-climate",
        "entities": {
            "epa"
        },
        "action_clusters": set(),
        "keywords": {
            "energy", "clean energy", "renewable", "renewables", "solar", "wind power",
            "power grid", "grid", "grids", "electricity", "battery storage", "climate",
            "climate change", "emissions", "carbon", "net-zero", "global warming", "oil", "gas",
            "petroleum", "fossil fuels", "green energy", "geothermal", "environment", "water",
            "water crisis", "conservation"
        }
    },
    {
        "name": "Policy & Law",
        "emoji": "⚖️",
        "slug": "policy-law",
        "entities": {
            "doj", "ftc", "fcc", "fda", "epa", "cisa", "fbi", "eu", "european commission",
            "donald trump", "joe biden"
        },
        "action_clusters": {"legal_regulatory"},
        "keywords": {
            "policy", "government", "law", "lawsuit", "sued", "suing", "court", "judge", "trial",
            "regulation", "regulatory", "regulators", "legislation", "bill", "congress", "senate",
            "white house", "executive order", "ban", "banned", "fine", "fined", "penalty",
            "sanctions", "compliance", "copyright", "patent", "legal", "illegal", "attorney",
            "justice department", "antitrust"
        }
    }
]

GENERAL_TOPIC: Dict[str, Any] = {
    "name": "General & Other",
    "emoji": "📰",
    "slug": "general-other",
    "entities": set(),
    "action_clusters": set(),
    "keywords": set(),
    "regex": None
}

# Compile keyword regex patterns for each topic once
for topic in TOPIC_TAXONOMY:
    sorted_kws = sorted(topic["keywords"], key=lambda k: -len(k))
    pats = [r"\b" + re.escape(kw) + r"\b" for kw in sorted_kws]
    topic["regex"] = re.compile("|".join(pats), re.IGNORECASE) if pats else None

ALL_TOPICS: List[Dict[str, Any]] = TOPIC_TAXONOMY + [GENERAL_TOPIC]
TOPIC_CATALOG: Dict[str, Dict[str, Any]] = {t["slug"]: t for t in ALL_TOPICS}


def classify_article_topic(article: Dict[str, Any]) -> str:
    """
    Classifies an article into the best matching topic from the taxonomy
    based on story signature entities, action clusters, keypoints, and keywords.
    Returns the slug of the matched topic or 'general-other'.
    """
    sig = article.get("story_signature")
    if not sig:
        sig = generate_story_signature(article.get("title") or "", article.get("summary") or "")
        article["story_signature"] = sig

    parsed = parse_story_signature(sig)
    sig_entities = set(parsed.get("entities", []))
    sig_cluster = parsed.get("cluster", "")
    sig_keys = set(parsed.get("keys", []))

    title_raw = article.get("title") or ""
    summary_raw = article.get("summary") or ""
    all_entities = sig_entities.union(extract_entities(f"{title_raw} {summary_raw}"))

    title_clean = clean_html_text(title_raw).lower()
    summary_clean = clean_html_text(summary_raw).lower()

    best_slug = None
    best_score = 0

    for topic in TOPIC_TAXONOMY:
        score = 0

        # Entity match (+3 per entity)
        matched_entities = all_entities.intersection(topic["entities"])
        score += len(matched_entities) * 3

        # Action cluster match (+2)
        if sig_cluster and sig_cluster in topic["action_clusters"]:
            score += 2

        # Keypoints match (+2 per key)
        matched_keys = sig_keys.intersection(topic["keywords"])
        score += len(matched_keys) * 2

        # Title keyword match (+2 per match)
        if topic.get("regex"):
            title_matches = len(topic["regex"].findall(title_clean))
            score += title_matches * 2

            # Summary keyword match (+1 per match, capped at 3)
            summary_matches = len(topic["regex"].findall(summary_clean))
            score += min(summary_matches, 3) * 1

        if score > best_score:
            best_score = score
            best_slug = topic["slug"]

    # Minimum threshold to qualify for a specific topic
    if best_score >= 2 and best_slug:
        return best_slug
    return "general-other"


async def build_interest_board(db, max_groups: int = 5) -> Dict[str, Any]:
    """
    Builds an Interest Board grouping unread articles into top topical clusters.
    
    1. Fetches unread articles (is_read = 0) with feed details.
    2. Decodes HTML fields, computes likelihood tiers and story signatures.
    3. Categorizes each article into predefined topical taxonomy.
    4. Selects top max_groups topics by article count, capturing remaining/unmatched
       articles in 'General & Other 📰' so no unread items are lost.
    5. Caps each group to max 25 articles, sorted by interest_score DESC then published_at DESC.
    """
    query = """
        SELECT a.*, 
               f.title as feed_title,
               f.favicon_url as feed_favicon_url,
               (SELECT COUNT(*) FROM articles ac WHERE ac.cluster_id = a.cluster_id) as cluster_count,
               (SELECT GROUP_CONCAT(DISTINCT f2.title) 
                FROM articles ac2 
                JOIN feeds f2 ON ac2.feed_id = f2.id 
                WHERE ac2.cluster_id = a.cluster_id AND ac2.id != a.id) as other_cluster_sources
        FROM articles a
        LEFT JOIN feeds f ON a.feed_id = f.id
        WHERE a.is_read = 0
        ORDER BY a.interest_score DESC, a.published_at DESC, a.id DESC
    """
    items = await db.fetch_all(query)
    if not items:
        return {"groups": []}

    likely_threshold, high_threshold, _, _ = await get_likelihood_thresholds(db)

    # Prepare and format article records matching ArticleResponse
    for item in items:
        item["is_read"] = bool(item.get("is_read", 0))
        item["is_starred"] = bool(item.get("is_starred", 0))
        item["feed_title"] = decode_html_text(item.get("feed_title")) or "Feed"
        item["title"] = decode_html_text(item.get("title"))
        item["summary"] = decode_html_text(item.get("summary"))
        if item.get("author"):
            item["author"] = decode_html_text(item.get("author"))
        if item.get("content"):
            item["content"] = decode_html_text(item.get("content"))

        raw_sources = item.pop("other_cluster_sources", None)
        if raw_sources:
            item["cluster_sources"] = [decode_html_text(s.strip()) for s in raw_sources.split(",") if s.strip()]
        else:
            item["cluster_sources"] = []

        item["cluster_count"] = item.get("cluster_count") or 1
        item["interest_score"] = float(item.get("interest_score") or 0.0)
        item["likelihood_tier"] = compute_likelihood_tier(item["interest_score"], likely_threshold, high_threshold)
        item["user_vote"] = int(item.get("user_vote") or 0)

        if not item.get("story_signature"):
            item["story_signature"] = generate_story_signature(item.get("title") or "", item.get("summary") or "")

    # Group articles into topic buckets
    grouped_articles: Dict[str, List[Dict[str, Any]]] = {t["slug"]: [] for t in ALL_TOPICS}
    for item in items:
        slug = classify_article_topic(item)
        grouped_articles[slug].append(item)

    # Identify specific topics with articles
    specific_slugs_with_articles = [
        t["slug"] for t in TOPIC_TAXONOMY if len(grouped_articles[t["slug"]]) > 0
    ]

    # Rank specific topics by article count DESC, then sum of interest_score DESC
    specific_slugs_with_articles.sort(
        key=lambda s: (
            len(grouped_articles[s]),
            sum(float(a.get("interest_score") or 0.0) for a in grouped_articles[s])
        ),
        reverse=True
    )

    general_articles = grouped_articles.get("general-other", [])

    if max_groups <= 0:
        max_groups = 5

    # Determine which topics are selected
    if len(specific_slugs_with_articles) + (1 if general_articles else 0) <= max_groups:
        # Everything fits within the requested max_groups limit
        selected_slugs = list(specific_slugs_with_articles)
        if general_articles:
            selected_slugs.append("general-other")
    else:
        if max_groups == 1:
            # When max_groups is 1, pick the single largest group
            candidates = list(specific_slugs_with_articles)
            if general_articles:
                candidates.append("general-other")
            candidates.sort(key=lambda s: len(grouped_articles[s]), reverse=True)
            selected_slugs = candidates[:1]
        else:
            num_specific_slots = max_groups - 1
            selected_specific = specific_slugs_with_articles[:num_specific_slots]
            unselected_specific = specific_slugs_with_articles[num_specific_slots:]

            # Fold remaining articles from unselected specific topics into General & Other
            for s in unselected_specific:
                grouped_articles["general-other"].extend(grouped_articles[s])

            selected_slugs = list(selected_specific)
            if grouped_articles["general-other"]:
                selected_slugs.append("general-other")

    # Build the final response list of groups
    groups = []
    for slug in selected_slugs:
        topic_info = TOPIC_CATALOG[slug]
        articles_in_group = grouped_articles[slug]

        # Sort by interest_score DESC, published_at DESC
        sorted_articles = sorted(
            articles_in_group,
            key=lambda a: (
                float(a.get("interest_score") or 0.0),
                str(a.get("published_at") or "")
            ),
            reverse=True
        )

        capped_articles = sorted_articles[:25]
        groups.append({
            "name": topic_info["name"],
            "emoji": topic_info["emoji"],
            "slug": topic_info["slug"],
            "article_count": len(capped_articles),
            "articles": capped_articles
        })

    return {"groups": groups}
