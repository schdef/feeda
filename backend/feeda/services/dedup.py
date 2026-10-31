import hashlib
import html
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Tracking parameters to strip during URL normalization
_TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ncid', 'ocid', 'ref', 'source', 'mc_cid', 'mc_eid',
    '_hsenc', '_hsmi', 'mkt_tok', 'oly_anon_id', 'oly_enc_id',
    'vero_id', 's_cid', 'icid', 'igshid',
}

def normalize_url(url: str) -> str:
    """Normalize URL by lowercasing, stripping tracking params, and standardizing scheme."""
    url = url.strip()
    parsed = urlparse(url.lower())
    # Normalize scheme to https
    scheme = 'https'
    # Strip tracking query parameters, keep meaningful ones (e.g., ?v= for YouTube)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
        # Sort params for consistent hashing
        query = urlencode(filtered, doseq=True) if filtered else ''
    else:
        query = ''
    # Rebuild URL without fragment, with cleaned query
    normalized = urlunparse((scheme, parsed.netloc, parsed.path.rstrip('/'), '', query, ''))
    return normalized

def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()

def clean_title(title: str) -> str:
    if not title:
        return ""
    # HTML unescape entities
    t = html.unescape(title)
    # Strip HTML tags
    t = re.sub(r'<[^>]+>', ' ', t)
    # Normalize smart quotes and apostrophes
    t = re.sub(r'[‘’,‛]', "'", t)
    t = re.sub(r'[“”,„,‟]', '"', t)
    # Strip domain suffixes like (bbc.com), (theverge.com), (spiegel.de), (news.ycombinator.com)
    t = re.sub(r'\s*\((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\)\s*$', '', t)
    # Strip site suffixes: " - Spiegel Online", " | TechCrunch", " » Blog", " — The Verge", " // Heise"
    t = re.sub(r'\s+[-–—|»/•]\s+.*$', '', t)
    # Strip prefixes iteratively like "[Update]", "Breaking:", "(Video)", "Ask HN:", "Show HN:", "Tell HN:", "Liveblog:", "Report:"
    while True:
        new_t = re.sub(r'^\s*(\[[^\]]*\]|\([^\)]*\)|(?:Ask|Show|Tell)\s+HN:?|BREAKING:?|UPDATE:?|Liveblog:?|Report:?)\s*', '', t, flags=re.IGNORECASE)
        if new_t == t:
            break
        t = new_t
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def word_shingles(title: str, n: int = 2) -> set:
    cleaned = clean_title(title).lower()
    words = re.findall(r'(?u)\b[^\W\d_]{2,}\b', cleaned)
    if not words:
        return set()
    if len(words) < n:
        return set(words)
    return set(" ".join(words[i:i+n]) for i in range(len(words) - n + 1))

def is_duplicate_title(title1: str, title2: str) -> bool:
    if not title1 or not title2:
        return False
    c1 = clean_title(title1).lower()
    c2 = clean_title(title2).lower()
    if c1 == c2:
        return True

    from .ranker import STOP_WORDS

    # Significant alphanumeric tokens (handles e.g. "iPhone 15", "GPT-4")
    t1_tokens = set(re.findall(r'(?u)\b\w{2,}\b', c1)) - STOP_WORDS
    t2_tokens = set(re.findall(r'(?u)\b\w{2,}\b', c2)) - STOP_WORDS
    if t1_tokens and t2_tokens:
        inter = len(t1_tokens.intersection(t2_tokens))
        union = len(t1_tokens.union(t2_tokens))
        min_len = min(len(t1_tokens), len(t2_tokens))
        j_tokens = inter / union
        overlap_ratio = inter / min_len if min_len > 0 else 0
        if j_tokens >= 0.55 or (overlap_ratio >= 0.70 and inter >= 3):
            return True

    w1 = set(re.findall(r'(?u)\b[^\W\d_]{2,}\b', c1))
    w2 = set(re.findall(r'(?u)\b[^\W\d_]{2,}\b', c2))
    if w1 and w2:
        j_words = len(w1.intersection(w2)) / len(w1.union(w2))
        if j_words >= 0.65:
            return True

    ws1 = word_shingles(c1, 2)
    ws2 = word_shingles(c2, 2)
    if ws1 and ws2:
        j_shingles = len(ws1.intersection(ws2)) / len(ws1.union(ws2))
        if j_shingles >= 0.55:
            return True

    cs1 = title_shingles(c1)
    cs2 = title_shingles(c2)
    if cs1 and cs2 and jaccard_similarity(cs1, cs2) >= 0.70:
        return True

    return False

def is_duplicate_article(a1: dict, a2: dict) -> bool:
    if not a1 or not a2:
        return False
    if a1.get('id') and a2.get('id') and a1['id'] == a2['id']:
        return True
    if a1.get('cluster_id') and a2.get('cluster_id') and a1['cluster_id'] == a2['cluster_id']:
        return True
    if a1.get('guid') and a2.get('guid') and a1['guid'] == a2['guid']:
        return True

    u1 = a1.get('url')
    u2 = a2.get('url')
    if u1 and u2:
        if normalize_url(u1) == normalize_url(u2):
            return True
        if a1.get('url_hash') and a2.get('url_hash') and a1['url_hash'] == a2['url_hash']:
            return True

    t1 = a1.get('title')
    t2 = a2.get('title')
    if t1 and t2 and is_duplicate_title(t1, t2):
        return True

    s1 = a1.get('content_simhash')
    s2 = a2.get('content_simhash')
    if s1 and s2 and s1 != 0 and s2 != 0:
        if hamming_distance(int(s1), int(s2)) <= 3:
            return True

    # Content / summary token overlap fallback if simhash is unavailable or borderline
    c1 = re.sub(r'<[^>]+>', ' ', a1.get('content') or a1.get('summary') or '').lower()
    c2 = re.sub(r'<[^>]+>', ' ', a2.get('content') or a2.get('summary') or '').lower()
    if c1 and c2:
        from .ranker import STOP_WORDS
        w1 = set(re.findall(r'(?u)\b\w{3,}\b', c1)) - STOP_WORDS
        w2 = set(re.findall(r'(?u)\b\w{3,}\b', c2)) - STOP_WORDS
        if len(w1) >= 5 and len(w2) >= 5:
            inter = len(w1.intersection(w2))
            min_len = min(len(w1), len(w2))
            if (inter / min_len >= 0.75) and inter >= 5:
                return True

    return False

def title_shingles(title: str, n: int = 3) -> set:
    clean = re.sub(r'[^a-z0-9]', '', clean_title(title).lower())
    return set([clean[i:i+n] for i in range(len(clean) - n + 1)]) if len(clean) >= n else set([clean])

def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b: return 0.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))

def compute_simhash(text: str) -> int:
    if not text: return 0
    # Strip HTML tags and decode HTML entities
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    cleaned = html.unescape(cleaned)
    words = re.findall(r'\w+', cleaned.lower())
    if not words:
        return 0

    v = [0] * 64
    if len(words) >= 3:
        for i in range(len(words) - 2):
            shingle = " ".join(words[i:i+3])
            h = int(hashlib.md5(shingle.encode()).hexdigest(), 16)
            for j in range(64):
                bit = (h >> j) & 1
                v[j] += 1 if bit else -1
    elif len(words) == 2:
        shingle = " ".join(words)
        h = int(hashlib.md5(shingle.encode()).hexdigest(), 16)
        for j in range(64):
            bit = (h >> j) & 1
            v[j] += 1 if bit else -1
    else:
        h = int(hashlib.md5(words[0].encode()).hexdigest(), 16)
        for j in range(64):
            bit = (h >> j) & 1
            v[j] += 1 if bit else -1
            
    simhash = 0
    for i in range(64):
        if v[i] > 0:
            simhash |= (1 << i)
    # Convert to signed 64-bit to fit SQLite INTEGER
    if simhash >= (1 << 63):
        simhash -= (1 << 64)
    return simhash

def hamming_distance(h1: int, h2: int) -> int:
    # Ensure we work with unsigned representation for XOR
    return bin((h1 ^ h2) & 0xFFFFFFFFFFFFFFFF).count('1')

async def update_cluster_primary(db, cluster_id: int):
    """Ensures the article with the earliest published_at (or fetched_at) is the primary_article_id."""
    earliest = await db.fetch_one("""
        SELECT id FROM articles 
        WHERE cluster_id = ? 
        ORDER BY datetime(COALESCE(published_at, fetched_at)) ASC, id ASC 
        LIMIT 1
    """, (cluster_id,))
    if earliest:
        await db.execute("UPDATE clusters SET primary_article_id = ? WHERE id = ?", (earliest['id'], cluster_id))
        return earliest['id']
    return None

async def find_duplicate(article: dict, db) -> int:
    guid = article.get('guid')
    if guid:
        row_guid = await db.fetch_one("SELECT id, cluster_id FROM articles WHERE guid = ?", (guid,))
        if row_guid:
            if row_guid.get('cluster_id'):
                return row_guid['cluster_id']
            return await create_cluster(db, row_guid['id'])

    uhash = url_hash(article['url'])
    # 1. Exact URL hash in any feed
    row = await db.fetch_one("SELECT id, cluster_id FROM articles WHERE url_hash = ?", (uhash,))
    if row:
        if row.get('cluster_id'):
            return row['cluster_id']
        return await create_cluster(db, row['id'])

    # 2. Title similarity against recent articles
    recent = await db.fetch_all("SELECT id, cluster_id, title FROM articles ORDER BY id DESC LIMIT 500")
    for r in recent:
        if is_duplicate_title(article['title'], r['title']):
            return r['cluster_id'] or await create_cluster(db, r['id'])

    # 3. Simhash similarity
    simhash_val = compute_simhash(article.get('content') or article.get('summary') or '')
    if simhash_val:
        recent_hashes = await db.fetch_all("SELECT id, cluster_id, content_simhash FROM articles WHERE content_simhash IS NOT NULL AND content_simhash != 0 ORDER BY id DESC LIMIT 500")
        for r in recent_hashes:
            if hamming_distance(simhash_val, r['content_simhash']) <= 3:
                return r['cluster_id'] or await create_cluster(db, r['id'])

    return None
    
async def create_cluster(db, article_id: int) -> int:
    cluster_id = await db.execute("INSERT INTO clusters (primary_article_id) VALUES (?)", (article_id,))
    await db.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cluster_id, article_id))
    await update_cluster_primary(db, cluster_id)
    return cluster_id
