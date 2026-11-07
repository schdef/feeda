import os
import re
import html
import json
import logging
from typing import List, Dict, Any, Optional, Set
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODELS = ["nvidia/nemotron-3.5-lightning:free", "liquid/lfm-2.5-2.6b:free", "meta-llama/llama-3.2-3b-instruct:free"]

# Gazetteer of prominent named entities (tech companies, auto brands, products, people, institutions)
KNOWN_ENTITIES = {
    # Automotive / Clean Energy
    "tesla", "cybertruck", "model 3", "model y", "model s", "model x", "roadster", "optimus", "supercharger",
    "rivian", "r1t", "r1s", "lucid", "byd", "ford", "gm", "general motors", "chevrolet", "volkswagen",
    "bmw", "mercedes", "audi", "porsche", "toyota", "honda", "hyundai", "kia", "waymo", "cruise", "zoox",
    # Big Tech / Platforms
    "apple", "iphone", "ipad", "macbook", "mac", "vision pro", "airpods", "apple watch", "ios", "macos",
    "google", "android", "pixel", "gemini", "deepmind", "youtube", "chrome", "chromebook", "waymo",
    "microsoft", "windows", "copilot", "xbox", "surface", "azure", "office 365",
    "meta", "facebook", "instagram", "threads", "whatsapp", "quest", "llama",
    "amazon", "aws", "alexa", "kindle", "prime",
    # AI & Semiconductors
    "openai", "chatgpt", "gpt-4", "gpt-4o", "gpt-5", "sora", "dall-e", "o1", "o3",
    "anthropic", "claude", "nvidia", "cuda", "geforce", "rtx", "blackwell", "hopper",
    "intel", "amd", "radeon", "ryzen", "qualcomm", "snapdragon", "arm", "tsmc", "asml",
    "deepseek", "mistral", "perplexity", "hugging face", "stability ai", "midjourney",
    # Space & Defense
    "spacex", "starlink", "falcon 9", "starship", "nasa", "esa", "boeing", "blue origin",
    # Social / Web / Dev
    "twitter", "x.com", "tiktok", "bytedance", "reddit", "github", "gitlab", "discord",
    "spotify", "netflix", "uber", "airbnb", "stripe", "paypal", "salesforce", "oracle",
    # Prominent Figures
    "elon musk", "sam altman", "jensen huang", "tim cook", "satya nadella", "sundar pichai",
    "mark zuckerberg", "jeff bezos", "bill gates", "donald trump", "joe biden",
    # Agencies / Institutions
    "doj", "sec", "ftc", "fcc", "fda", "epa", "cisa", "fbi", "eu", "european commission", "federal reserve"
}

# Aliases and entity normalizations
ENTITY_ALIASES = {
    "musk": "elon musk",
    "altman": "sam altman",
    "zuckerberg": "mark zuckerberg",
    "zuck": "mark zuckerberg",
    "pichai": "sundar pichai",
    "nadella": "satya nadella",
    "cook": "tim cook",
    "huang": "jensen huang",
    "fb": "facebook",
    "ig": "instagram",
    "x": "twitter",
    "chat gpt": "chatgpt",
    "gpt4": "gpt-4",
    "gpt4o": "gpt-4o",
    "cyber truck": "cybertruck",
    "star link": "starlink",
    "deep mind": "deepmind",
    "mac book": "macbook"
}

# Semantic Action Clusters mapping actions to broad event categories
ACTION_CLUSTERS = {
    "production_halt_reduce": {
        "wind_down": [r"\bwind(?:ing|s)?\s+down\b", r"\bwound\s+down\b", r"\bwind-down\b"],
        "production_cut": [r"\b(?:production|output)\s+cuts?\b", r"\bcut(?:ting|s)?\s+(?:production|output)\b", r"\bslash(?:ing|es)?\s+(?:production|output)\b"],
        "pause": [r"\bpaus(?:ing|e|es|ed)\b", r"\bhalt(?:ing|s|ed)?\b", r"\bfreez(?:ing|e|es|ed)\b", r"\bstandstill\b"],
        "slow_down": [r"\bslow(?:ing|s)?\s+down\b", r"\bslowdown\b"],
        "shut_down": [r"\bshut(?:ting|s)?\s+down\b", r"\bshutdown\b"],
        "cut": [r"\bcuts?\b", r"\bcutting\b", r"\bslash(?:ing|es|ed)?\b", r"\breduc(?:ing|e|es|ed|tion)\b"],
        "delay": [r"\bdelay(?:ing|s|ed)?\b", r"\bpostpon(?:ing|e|es|ed)\b", r"\bpush(?:ing|es|ed)?\s+back\b"],
        "cancel": [r"\bcancel(?:l)?(?:ing|s|ed|ation)?\b", r"\bscrap(?:ping|s|ped)?\b", r"\bditch(?:ing|es|ed)?\b"],
        "stop": [r"\bstop(?:ping|s|ped)?\b", r"\bceas(?:ing|e|es|ed)\b"]
    },
    "product_launch_release": {
        "launch": [r"\blaunch(?:ing|es|ed)?\b"],
        "release": [r"\breleas(?:ing|e|es|ed)\b"],
        "unveil": [r"\bunveil(?:ing|s|ed)?\b"],
        "announce": [r"\bannounc(?:ing|e|es|ed|ement)\b"],
        "debut": [r"\bdebut(?:ing|s|ed)?\b"],
        "roll_out": [r"\broll(?:ing|s)?\s+out\b", r"\brollout\b"],
        "reveal": [r"\breveal(?:ing|s|ed)?\b"],
        "ship": [r"\bship(?:ping|s|ped)?\b"]
    },
    "business_deal": {
        "acquire": [r"\bacquir(?:ing|e|es|ed|isition)\b", r"\bbuyout\b", r"\btakeover\b"],
        "buy": [r"\bbuy(?:ing|s)?\b", r"\bbought\b", r"\bpurchas(?:ing|e|es|ed)\b"],
        "invest": [r"\binvest(?:ing|s|ed|ment)?\b", r"\bfund(?:ing|ed|s)?\b"],
        "raise": [r"\brais(?:ing|e|es|ed)\b", r"\bround\b"],
        "partner": [r"\bpartner(?:ing|s|ed|ship)?\b", r"\bdeal\b", r"\balliance\b"],
        "sell": [r"\bsell(?:ing|s)?\b", r"\bsold\b", r"\bdivest(?:ing|s|ed|ment)?\b"]
    },
    "legal_regulatory": {
        "sue": [r"\bsu(?:ing|es|ed)?\b", r"\blawsuit\b", r"\blitigat(?:ing|ion)\b"],
        "investigate": [r"\binvestigat(?:ing|e|es|ed|ion)\b", r"\bprobe(?:ing|s|ed)?\b", r"\binquiry\b"],
        "fine": [r"\bfine(?:ing|s|ed)?\b", r"\bpenalt(?:y|ies)\b"],
        "ban": [r"\bban(?:ning|s|ned)?\b", r"\bblock(?:ing|s|ed)?\b"],
        "indict": [r"\bindict(?:ing|s|ed|ment)\b", r"\bcharg(?:ing|e|es|ed)\b"]
    },
    "workforce_leadership": {
        "layoff": [r"\blay(?:ing)?\s+off\b", r"\blayoffs?\b", r"\bcut(?:ting)?\s+jobs\b", r"\bjob\s+cuts\b"],
        "resign": [r"\bresign(?:ing|s|ed|ation)?\b", r"\bstep(?:ping|s)?\s+down\b", r"\bdeparts?\b"],
        "fire": [r"\bfir(?:ing|e|es|ed)\b", r"\boust(?:ing|ed|s)?\b"],
        "hire": [r"\bhir(?:ing|e|es|ed)\b", r"\bappoint(?:ing|s|ed|ment)?\b"]
    },
    "security_incident": {
        "leak": [r"\bleak(?:ing|s|ed)?\b", r"\bmemo\b", r"\bleaked\s+memo\b"],
        "hack": [r"\bhack(?:ing|ed|er|s)?\b", r"\bbreach(?:ing|ed|es)?\b"],
        "vulnerability": [r"\bvulnerabilit(?:y|ies)\b", r"\bflaw\b", r"\bexploit(?:ing|ed|s)?\b", r"\bzero-day\b"],
        "outage": [r"\boutage\b", r"\bdown\b", r"\bcrash(?:ing|ed|es)?\b"]
    },
    "recall_safety": {
        "recall": [r"\brecall(?:ing|s|ed)?\b"],
        "defect": [r"\bdefect(?:ive|s)?\b", r"\bsafety\s+(?:hazard|issue|concern)\b"]
    }
}

# Stopwords for filtering keypoints
STOP_WORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'have', 'from', 'but', 'not',
    'are', 'was', 'were', 'will', 'by', 'der', 'die', 'das', 'und', 'fuer', 'für',
    'mit', 'auf', 'von', 'den', 'dem', 'ein', 'eine', 'einer', 'eines', 'einem',
    'einen', 'ist', 'sind', 'war', 'nicht', 'wie', 'als', 'ueber', 'über',
    'nach', 'bei', 'aus', 'durch', 'oder', 'aber', 'auch', 'zur', 'zum',
    'sich', 'dass', 'has', 'had', 'been', 'about', 'after', 'again', 'against',
    'all', 'any', 'could', 'did', 'does', 'doing', 'down', 'each', 'few',
    'more', 'most', 'other', 'over', 'same', 'some', 'such', 'than', 'too',
    'very', 'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why',
    'would', 'says', 'said', 'saying', 'new', 'first', 'just', 'into', 'its',
    'their', 'they', 'them', 'these', 'those', 'there', 'here', 'may', 'might',
    'must', 'can', 'should', 'report', 'reports', 'reported', 'according'
}

# Pre-compiled high-performance regex patterns
_ENTITY_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(e) for e in sorted(KNOWN_ENTITIES, key=lambda x: -len(x))) + r')\b')
_ALIAS_MAP = dict(ENTITY_ALIASES)
_ALIAS_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(a) for a in sorted(ENTITY_ALIASES.keys(), key=lambda x: -len(x))) + r')\b')
_CAMEL_REGEX = re.compile(r'\b[A-Z][a-z]+[A-Z]\w*\b')
_ACRONYM_REGEX = re.compile(r'\b[A-Z]{2,6}\b')

COMPILED_ACTION_CLUSTERS = {
    cluster_name: {
        action_name: [re.compile(p) for p in patterns]
        for action_name, patterns in action_map.items()
    }
    for cluster_name, action_map in ACTION_CLUSTERS.items()
}

def clean_html_text(text: Optional[str]) -> str:
    """Unescapes HTML entities twice and strips HTML tags and excess whitespace."""
    if not text:
        return ""
    unescaped = html.unescape(html.unescape(str(text)))
    no_html = re.sub(r'<[^>]+>', ' ', unescaped)
    return re.sub(r'\s+', ' ', no_html).strip()

def extract_entities(text: str) -> List[str]:
    """
    Extracts named entities (companies, products, persons, institutions)
    using known gazetteers, aliases, acronyms, and CamelCase patterns.
    """
    if not text:
        return []

    cleaned = clean_html_text(text)
    lower_text = cleaned.lower()
    entities: Set[str] = set()

    # 1. Single regex pass for all known entities
    for m in _ENTITY_REGEX.finditer(lower_text):
        entities.add(m.group(0))

    # 2. Single regex pass for all aliases
    for m in _ALIAS_REGEX.finditer(lower_text):
        canon = _ALIAS_MAP.get(m.group(0))
        if canon:
            entities.add(canon)

    # 3. CamelCase / MixedCase patterns (e.g. ChatGPT, DeepSeek, YouTube)
    for cm in _CAMEL_REGEX.findall(cleaned):
        low = cm.lower()
        if low not in STOP_WORDS:
            entities.add(low)

    # 4. Acronyms (ALL CAPS, 2-6 chars, e.g. NASA, DOJ, SEC, TSMC, BYD, EV)
    for ac in _ACRONYM_REGEX.findall(cleaned):
        low = ac.lower()
        if low in KNOWN_ENTITIES or (len(ac) >= 3 and low not in STOP_WORDS):
            entities.add(low)

    return sorted(list(entities))

def extract_actions(text: str) -> Dict[str, Any]:
    """
    Extracts event action predicates and assigns the primary action cluster.
    """
    if not text:
        return {"primary_cluster": "", "actions": []}

    lower_text = clean_html_text(text).lower()
    matched_actions: Set[str] = set()
    cluster_counts: Dict[str, int] = {}

    for cluster_name, action_map in COMPILED_ACTION_CLUSTERS.items():
        for action_name, patterns in action_map.items():
            for pat in patterns:
                if pat.search(lower_text):
                    matched_actions.add(action_name)
                    cluster_counts[cluster_name] = cluster_counts.get(cluster_name, 0) + 1
                    break

    primary_cluster = ""
    if cluster_counts:
        # Highest match count cluster
        primary_cluster = max(cluster_counts.items(), key=lambda kv: kv[1])[0]

    return {
        "primary_cluster": primary_cluster,
        "actions": sorted(list(matched_actions))
    }

def extract_keypoints(text: str, max_points: int = 5) -> List[str]:
    """
    Extracts salient normalized keywords (excluding entities and stop words).
    """
    if not text:
        return []

    cleaned = clean_html_text(text).lower()
    tokens = re.findall(r'(?u)\b[a-z0-9_-]{3,}\b', cleaned)
    filtered = []
    for t in tokens:
        if t not in STOP_WORDS and not t.isdigit() and len(t) >= 3:
            filtered.append(t)

    # Deduplicate while preserving order of significance / frequency
    seen = set()
    unique_tokens = []
    for t in filtered:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)
        if len(unique_tokens) >= max_points:
            break

    return unique_tokens

def generate_story_signature(title: str, text: str = "") -> str:
    """
    Generates a deterministic entity-action-keypoint story signature string:
    e.g. 'entity:cybertruck,tesla|cluster:production_halt_reduce|action:cut,pause,wind_down|keys:memo,production'
    """
    combined = f"{title}. {text[:600]}"
    entities = extract_entities(combined)
    action_data = extract_actions(combined)
    keypoints = extract_keypoints(combined, max_points=4)

    ent_str = ",".join(entities)
    cluster_str = action_data.get("primary_cluster", "")
    act_str = ",".join(action_data.get("actions", []))
    key_str = ",".join(keypoints)

    return f"entity:{ent_str}|cluster:{cluster_str}|action:{act_str}|keys:{key_str}"

def parse_story_signature(sig: str) -> Dict[str, Any]:
    """Parses a serialized story signature string into structured parts."""
    if not sig:
        return {"entities": [], "cluster": "", "actions": [], "keys": []}

    parts = sig.split("|")
    res = {"entities": [], "cluster": "", "actions": [], "keys": []}
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            v = v.strip()
            if k == "entity":
                res["entities"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k == "cluster":
                res["cluster"] = v
            elif k == "action":
                res["actions"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k == "keys":
                res["keys"] = [x.strip() for x in v.split(",") if x.strip()]

    return res

def are_signatures_duplicate(sig1: str, sig2: str) -> bool:
    """
    Evaluates whether two story signatures describe the exact same event.
    """
    if not sig1 or not sig2:
        return False

    s1 = parse_story_signature(sig1)
    s2 = parse_story_signature(sig2)

    ents1 = set(s1["entities"])
    ents2 = set(s2["entities"])
    shared_ents = ents1.intersection(ents2)

    if not shared_ents:
        return False

    # Check for specific anchor entities (like cybertruck, starlink, vision pro, chatgpt)
    specific_anchors = {"cybertruck", "starlink", "vision pro", "chatgpt", "sora", "claude", "blackwell", "deepseek"}
    has_anchor = bool(shared_ents.intersection(specific_anchors))

    cluster1 = s1["cluster"]
    cluster2 = s2["cluster"]
    shared_actions = set(s1["actions"]).intersection(set(s2["actions"]))
    shared_keys = set(s1["keys"]).intersection(set(s2["keys"]))

    # Rule A: Same anchor entity + same action cluster (e.g. Cybertruck + production_halt_reduce)
    if has_anchor and cluster1 and cluster1 == cluster2:
        return True

    # Rule B: >= 2 shared entities + compatible action cluster or shared action
    if len(shared_ents) >= 2:
        if cluster1 and cluster1 == cluster2:
            return True
        if shared_actions:
            return True
        if len(shared_keys) >= 1:
            return True

    # Rule C: Shared anchor + shared action or >= 2 shared keypoints
    if has_anchor and (shared_actions or len(shared_keys) >= 2):
        return True

    # Rule D: 1 shared entity + same action cluster + shared actions
    if shared_ents and cluster1 and cluster1 == cluster2 and shared_actions:
        return True

    return False

def generate_local_summary(title: str, content: str = "", summary: str = "") -> str:
    """
    100% offline semantic summary synthesizer.
    Cleans feed text, extracts proposition core, and formats an executive summary.
    """
    c_title = clean_html_text(title)
    body_text = clean_html_text(content or summary or "")

    # Clean site/author prefixes from title
    c_title = re.sub(r'^(?:\[[^\]]*\]|\([^\)]*\)|Ask HN:|Show HN:|BREAKING:|UPDATE:|Liveblog:|Report:)\s*', '', c_title, flags=re.IGNORECASE)
    # Question conversion (e.g. "Is Tesla winding down Cybertruck? Leaked memo suggests pause" -> statement)
    if c_title.startswith("Is ") or c_title.startswith("Are ") or c_title.startswith("Will "):
        c_title = re.sub(r'^(?:Is|Are|Will)\s+', 'Reports indicate ', c_title)
        c_title = c_title.replace("?", ".")

    # Split body into sentences and pick the most informative non-boilerplate sentence
    sentences = re.split(r'(?<=[.!?])\s+', body_text)
    good_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 30:
            continue
        # Skip feed boilerplate
        if re.search(r'\b(?:subscribe|sign up|read more|appeared first on|click here|all rights reserved|copyright)\b', s_clean, re.IGNORECASE):
            continue
        good_sentences.append(s_clean)
        if len(good_sentences) >= 2:
            break

    if good_sentences:
        candidate_body = " ".join(good_sentences)
        # Avoid verbatim repetition if title is already in candidate_body
        if c_title.lower() in candidate_body.lower():
            return candidate_body
        return f"{c_title.rstrip('.')}. {candidate_body}"

    return c_title

async def generate_llm_summary(title: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Queries OpenRouter LLM for structured enrichment if API key is present.
    Returns None on failure or timeout so offline fallback takes over immediately.
    """
    if not OPENROUTER_API_KEY:
        return None

    prompt = (
        "You are an expert news analyst. Provide a 1-sentence executive summary and identify "
        "named entities and the main action event.\n"
        "Return ONLY JSON: {\"summary\": str, \"entities\": [str], \"action\": str, \"action_cluster\": str}"
    )
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    input_text = f"Title: {title}\nBody: {text[:500]}"

    for model in DEFAULT_MODELS:
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_text}
            ],
            "response_format": {"type": "json_object"}
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=data)
                resp.raise_for_status()
                res = resp.json()
                content_str = res['choices'][0]['message']['content']
                return json.loads(content_str)
        except Exception as e:
            logger.debug(f"OpenRouter summary attempt failed on model {model}: {e}")
            continue

    return None

def analyze_article_content(title: str, content_or_summary: str = "") -> Dict[str, Any]:
    """
    Synchronous offline analysis for article enrichment.
    """
    ai_summary = generate_local_summary(title, content=content_or_summary)
    story_sig = generate_story_signature(title, content_or_summary)
    entities = extract_entities(f"{title} {content_or_summary}")
    action_info = extract_actions(f"{title} {content_or_summary}")
    keypoints = extract_keypoints(f"{title} {content_or_summary}")

    return {
        "ai_summary": ai_summary,
        "story_signature": story_sig,
        "entities": entities,
        "action_cluster": action_info.get("primary_cluster", ""),
        "actions": action_info.get("actions", []),
        "keypoints": keypoints
    }

async def analyze_article(title: str, content: str = "", summary: str = "") -> Dict[str, Any]:
    """
    Asynchronous analysis with optional OpenRouter LLM enrichment.
    Falls back gracefully to 100% offline local extraction.
    """
    body = content or summary or ""
    llm_res = None
    if OPENROUTER_API_KEY:
        try:
            llm_res = await generate_llm_summary(title, body)
        except Exception:
            llm_res = None

    if llm_res and isinstance(llm_res, dict) and llm_res.get("summary"):
        ai_summary = llm_res["summary"]
        story_sig = generate_story_signature(title, body)
        return {
            "ai_summary": ai_summary,
            "story_signature": story_sig,
            "entities": llm_res.get("entities", extract_entities(f"{title} {body}")),
            "action_cluster": llm_res.get("action_cluster", ""),
            "actions": [llm_res.get("action")] if llm_res.get("action") else [],
            "keypoints": extract_keypoints(f"{title} {body}")
        }

    return analyze_article_content(title, body)

def are_ai_summaries_duplicate(sum1: Optional[str], sum2: Optional[str], t1: str = "", t2: str = "") -> bool:
    """
    Compares two AI-analyzed summaries using token overlap, entity alignment, and jaccard similarity.
    """
    if not sum1 or not sum2:
        return False

    c1 = clean_html_text(sum1).lower()
    c2 = clean_html_text(sum2).lower()

    if c1 == c2:
        return True

    words1 = set(re.findall(r'(?u)\b[a-z0-9_-]{3,}\b', c1)) - STOP_WORDS
    words2 = set(re.findall(r'(?u)\b[a-z0-9_-]{3,}\b', c2)) - STOP_WORDS

    if not words1 or not words2:
        return False

    inter = len(words1.intersection(words2))
    union = len(words1.union(words2))
    min_len = min(len(words1), len(words2))

    jaccard = inter / union if union > 0 else 0
    overlap_ratio = inter / min_len if min_len > 0 else 0

    # High Jaccard threshold
    if jaccard >= 0.45:
        return True

    # High overlap with common anchor entities
    ent1 = set(extract_entities(sum1 + " " + t1))
    ent2 = set(extract_entities(sum2 + " " + t2))
    shared_ents = ent1.intersection(ent2)

    specific_anchors = {"cybertruck", "starlink", "vision pro", "chatgpt", "sora", "claude", "blackwell", "deepseek"}
    has_anchor = bool(shared_ents.intersection(specific_anchors))

    if shared_ents:
        if (len(shared_ents) >= 2 or has_anchor) and (jaccard >= 0.20 or (overlap_ratio >= 0.25 and inter >= 3)):
            return True
        if jaccard >= 0.30 or (overlap_ratio >= 0.45 and inter >= 3):
            return True

    return False
