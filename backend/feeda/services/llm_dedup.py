import os
import json
import logging
import asyncio
import httpx
from typing import List, Dict, Any
from .dedup import create_cluster, is_duplicate_article

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = ["nvidia/nemotron-3.5-lightning:free", "liquid/lfm-2.5-2.6b:free"]

_evaluated_hashes = set()

async def get_clusters_from_llm(unclustered_payload: List[Dict]) -> Dict:
    if not OPENROUTER_API_KEY:
        return {"clusters": []}

    prompt = (
        "You are a news deduplication system. Identify articles reporting the same news event/story. "
        "Return JSON format: {\"clusters\": [{\"primary_id\": int, \"duplicate_ids\": [int, ...], \"topic\": str}]}"
    )
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for model in MODELS:
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(unclustered_payload)}
            ],
            "response_format": {"type": "json_object"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(OPENROUTER_URL, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content']
                return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM dedup failed with model {model}: {e}")
            continue
            
    return {"clusters": []}

async def cluster_unclustered_articles_background(db):
    try:
        query = """
            SELECT id, title, summary
            FROM articles
            WHERE cluster_id IS NULL AND is_read = 0
            ORDER BY published_at DESC
            LIMIT 40
        """
        unclustered = await db.fetch_all(query)
        if len(unclustered) <= 1:
            return

        payload = [
            {
                "id": a["id"], 
                "title": a["title"], 
                "summary": (a.get("summary") or "")[:150]
            }
            for a in unclustered
        ]

        payload_hash = hash(str([a["id"] for a in unclustered]))
        if payload_hash in _evaluated_hashes:
            return
        _evaluated_hashes.add(payload_hash)

        llm_result = await get_clusters_from_llm(payload)
        clusters = llm_result.get("clusters", [])

        for cluster in clusters:
            primary_id = cluster.get("primary_id")
            duplicate_ids = cluster.get("duplicate_ids", [])
            
            if not primary_id or not duplicate_ids:
                continue
                
            cluster_id = await create_cluster(db, primary_id)
            
            for dup_id in duplicate_ids:
                await db.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cluster_id, dup_id))
            
            from .dedup import update_cluster_primary
            await update_cluster_primary(db, cluster_id)
    except Exception as e:
        logger.error(f"Error in background clustering: {e}")

def _merge_duplicate(primary: Dict, duplicate: Dict):
    feed_title = duplicate.get("feed_title") or "Unknown"
    sources = primary.get("cluster_sources")
    if sources is None:
        sources = []

    is_different_article = (duplicate.get("id") and primary.get("id") and duplicate["id"] != primary["id"]) or (feed_title not in sources and feed_title != primary.get("feed_title"))
    if is_different_article:
        added_count = duplicate.get("cluster_count", 1)
        primary["cluster_count"] = primary.get("cluster_count", 1) + (added_count if added_count > 0 else 1)
    
    if feed_title != primary.get("feed_title") and feed_title not in sources:
        sources.append(feed_title)
    for s in duplicate.get("cluster_sources") or []:
        if s != primary.get("feed_title") and s not in sources:
            sources.append(s)
    primary["cluster_sources"] = sources

def deduplicate_articles_sync(articles: List[Dict]) -> List[Dict]:
    if not articles:
        return articles

    from .dedup import normalize_url, clean_title
    import re

    def normalize_title_key(t: str) -> str:
        c = clean_title(t or "").lower()
        return re.sub(r'[^a-z0-9]', '', c)

    grouped_by_cid = {}
    seen_ids = set()
    seen_urls = set()
    seen_titles = {}
    deduplicated_list = []

    for a in articles:
        aid = a.get("id")
        cid = a.get("cluster_id")
        u = a.get("url")
        norm_u = normalize_url(u) if u else None
        norm_t = normalize_title_key(a.get("title"))

        duplicate_primary = None

        # 1. Match by exact ID
        if aid is not None and aid in seen_ids:
            for accepted in deduplicated_list:
                if accepted.get("id") == aid:
                    duplicate_primary = accepted
                    break

        # 2. Match by cluster_id
        if duplicate_primary is None and cid is not None and cid in grouped_by_cid:
            duplicate_primary = grouped_by_cid[cid]

        # 3. Match by normalized URL
        if duplicate_primary is None and norm_u and norm_u in seen_urls:
            for accepted in deduplicated_list:
                if accepted.get("url") and normalize_url(accepted["url"]) == norm_u:
                    duplicate_primary = accepted
                    break

        # 4. Match by normalized title
        if duplicate_primary is None and norm_t and len(norm_t) > 10 and norm_t in seen_titles:
            duplicate_primary = seen_titles[norm_t]

        # 5. Fuzzy match using is_duplicate_article
        if duplicate_primary is None:
            for accepted in deduplicated_list:
                if is_duplicate_article(a, accepted):
                    duplicate_primary = accepted
                    break

        if duplicate_primary is not None:
            _merge_duplicate(duplicate_primary, a)
            if cid is not None and duplicate_primary.get("cluster_id") is None:
                duplicate_primary["cluster_id"] = cid
                grouped_by_cid[cid] = duplicate_primary
            continue

        # Unique article! Add to accepted
        if cid is not None:
            grouped_by_cid[cid] = a
        if aid is not None:
            seen_ids.add(aid)
        if norm_u:
            seen_urls.add(norm_u)
        if norm_t and len(norm_t) > 10:
            seen_titles[norm_t] = a

        if "cluster_sources" not in a or a["cluster_sources"] is None:
            a["cluster_sources"] = []
        feed_title = a.get("feed_title") or "Unknown"
        if feed_title not in a["cluster_sources"]:
            a["cluster_sources"].append(feed_title)
        if "cluster_count" not in a or not a["cluster_count"]:
            a["cluster_count"] = 1
        deduplicated_list.append(a)

    return deduplicated_list

async def deduplicate_articles_llm(articles: List[Dict], db=None) -> List[Dict]:
    return deduplicate_articles_sync(articles)
