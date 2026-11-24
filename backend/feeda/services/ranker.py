import asyncio
import re
import math
from datetime import datetime
from dateutil import parser

_rescore_in_progress = False
_rescore_requested = False
_rescore_loop = None

STOP_WORDS = {
    # English functional / filler words
    'the', 'and', 'for', 'with', 'that', 'this', 'have', 'from', 'but', 'not',
    'are', 'was', 'were', 'will', 'by', 'its', 'it', 'has', 'had', 'having',
    'more', 'most', 'can', 'could', 'would', 'shall', 'should', 'may', 'might',
    'must', 'one', 'two', 'three', 'first', 'after', 'before', 'over', 'under',
    'into', 'onto', 'than', 'then', 'been', 'being', 'there', 'their', 'they',
    'them', 'these', 'those', 'about', 'also', 'such', 'some', 'any', 'other',
    'only', 'very', 'just', 'even', 'now', 'new', 'out', 'how', 'what',
    'when', 'where', 'which', 'who', 'whom', 'why', 'all', 'both', 'each', 'few',
    # German functional / filler words
    'der', 'die', 'das', 'und', 'fuer', 'für', 'mit', 'auf', 'von', 'den',
    'dem', 'ein', 'eine', 'einer', 'eines', 'einem', 'einen', 'ist', 'sind',
    'war', 'nicht', 'wie', 'als', 'ueber', 'über', 'nach', 'bei', 'aus',
    'durch', 'oder', 'aber', 'auch', 'zur', 'zum', 'sich', 'dass', 'hat',
    'haben', 'hatte', 'hatten', 'mehr', 'kann', 'können', 'koennen', 'konnte',
    'konnten', 'muss', 'müssen', 'muessen', 'musste', 'mussten', 'soll',
    'sollen', 'sollte', 'sollten', 'will', 'wollen', 'wollte', 'wollten',
    'wird', 'werden', 'wurde', 'wurden', 'dieser', 'dieses', 'diesem', 'diesen',
    'diese', 'jede', 'jeder', 'jedes', 'jedem', 'jeden', 'alle', 'aller',
    'alles', 'allem', 'allen', 'noch', 'schon', 'sehr', 'immer', 'wieder',
    'beim', 'unter', 'vor', 'zwischen', 'gegen', 'ohne', 'sein', 'seine',
    'seiner', 'seinem', 'seinen', 'seines', 'ihr', 'ihre', 'ihrer', 'ihrem',
    'ihren', 'ihres', 'wir', 'uns', 'unser', 'unsere', 'euch', 'euer', 'eure'
}

async def prune_stop_words_from_term_weights(db) -> int:
    if not STOP_WORDS:
        return 0
    placeholders = ",".join("?" for _ in STOP_WORDS)
    row = await db.fetch_one(
        f"SELECT COUNT(*) as c FROM term_weights WHERE term IN ({placeholders})",
        tuple(STOP_WORDS),
    )
    count = row["c"] if row and row.get("c") else 0
    if count > 0:
        await db.execute(
            f"DELETE FROM term_weights WHERE term IN ({placeholders})",
            tuple(STOP_WORDS),
        )
    return count

def extract_terms(text: str) -> list:
    if not text:
        return []
    clean = re.sub(r'<[^>]+>', ' ', text.lower())
    words = re.findall(r'(?u)\b[a-zäöüß]{3,}\b', clean)
    return [w for w in words if w not in STOP_WORDS]

async def update_feed_affinity(feed_id: int, action: str, db):
    if not feed_id:
        return
    positive_actions = {'open_website', 'click_through', 'star', 'vote_up', 'read_long', 'open_article', 'read', 'save_to_board'}
    if action not in positive_actions:
        return

    row = await db.fetch_one("SELECT articles_received, articles_read FROM feed_affinity WHERE feed_id = ?", (feed_id,))
    count_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM articles WHERE feed_id = ?", (feed_id,))
    total_articles = count_row['cnt'] if count_row and count_row['cnt'] else 1

    if row:
        articles_received = max(row['articles_received'], total_articles)
        articles_read = row['articles_read'] + 1
    else:
        articles_received = max(1, total_articles)
        articles_read = 1

    if articles_received < articles_read:
        articles_received = articles_read

    affinity_score = min(1.0, max(0.1, (articles_read + 1.0) / (articles_received + 2.0) * 1.5))

    await db.execute("""
        INSERT INTO feed_affinity (feed_id, articles_received, articles_read, affinity_score)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(feed_id) DO UPDATE SET
            articles_received = excluded.articles_received,
            articles_read = excluded.articles_read,
            affinity_score = excluded.affinity_score
    """, (feed_id, articles_received, articles_read, affinity_score))

async def update_term_weights(article_id: int, action: str, db):
    weights = {
        'save_to_board': 4.0,
        'star': 3.5,
        'open_website': 3.0,
        'click_through': 2.5,
        'open_article': 2.0,
        'vote_up': 2.0,
        'read': 1.5,
        'read_long': 1.5,
        'read_medium': 0.5,
        'vote_down': -3.0,
        'skip': -0.2,
        'read_short': -0.5,
        'unstar': -1.0
    }
    weight = weights.get(action, 0.0)

    article = await db.fetch_one("SELECT feed_id, title, summary, content FROM articles WHERE id = ?", (article_id,))
    if not article:
        return

    if article.get('feed_id'):
        await update_feed_affinity(article['feed_id'], action, db)

    if weight == 0.0:
        return

    terms = set(extract_terms((article.get('title') or "") + " " + (article.get('summary') or "") + " " + (article.get('content') or "")))
    if not terms:
        return

    if weight > 0:
        query = """
            INSERT INTO term_weights (term, positive_score) VALUES (?, ?)
            ON CONFLICT(term) DO UPDATE SET positive_score = positive_score + ?, updated_at = CURRENT_TIMESTAMP
        """
        params_list = [(term, weight, weight) for term in terms]
    else:
        w = abs(weight)
        query = """
            INSERT INTO term_weights (term, negative_score) VALUES (?, ?)
            ON CONFLICT(term) DO UPDATE SET negative_score = negative_score + ?, updated_at = CURRENT_TIMESTAMP
        """
        params_list = [(term, w, w) for term in terms]

    if hasattr(db, "execute_many"):
        await db.execute_many(query, params_list)
    elif getattr(db, "_conn", None) is not None:
        await db._conn.executemany(query, params_list)
        await db._conn.commit()
    else:
        for params in params_list:
            await db.execute(query, params)


async def score_article(
    article: dict,
    db,
    term_weights_map: dict | None = None,
    feed_affinity_map: dict | None = None,
    starred_counts_map: dict | None = None,
) -> float:
    terms = set(extract_terms((article.get('title') or "") + " " + (article.get('summary') or "") + " " + (article.get('content') or "")))
    s_bayes = 0.0
    if terms:
        if term_weights_map is not None:
            for term in terms:
                tw = term_weights_map.get(term)
                if tw is not None:
                    if isinstance(tw, dict):
                        s_bayes += float(tw['positive_score']) - float(tw['negative_score'])
                    else:
                        s_bayes += float(tw[0]) - float(tw[1])
        else:
            terms_list = list(terms)
            chunk_size = 500
            for start in range(0, len(terms_list), chunk_size):
                chunk = terms_list[start:start + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = await db.fetch_all(
                    f"SELECT term, positive_score, negative_score FROM term_weights WHERE term IN ({placeholders})",
                    tuple(chunk),
                )
                for row in rows:
                    s_bayes += float(row['positive_score']) - float(row['negative_score'])

        # Log-scaled length damping: rewards rich content without letting long text overwhelm concise news
        norm_factor = math.log(10 + len(terms)) / math.log(25)  # ~1.0 around 15 terms
        s_bayes = s_bayes / max(0.5, norm_factor)

    s_freshness = 1.0
    if article.get('published_at'):
        try:
            pub = parser.parse(article['published_at']).replace(tzinfo=None)
            hours_old = (datetime.utcnow() - pub).total_seconds() / 3600.0
            # 6 months = 182.5 days * 24 hours = 4380 hours
            if hours_old > 4380:
                return 0.0
            if hours_old > 0:
                s_freshness = math.exp(-0.0288 * hours_old) # half-life 24h
        except Exception:
            pass

    s_explicit = float(article.get('user_vote', 0)) * 2.0
    if article.get('is_starred'):
        s_explicit += 3.5

    s_feed = 0.5
    s_starred_boost = 0.0
    feed_id = article.get('feed_id')
    if feed_id:
        if feed_affinity_map is not None:
            affinity_val = feed_affinity_map.get(feed_id)
            if affinity_val is not None:
                s_feed = float(affinity_val)
        else:
            feed_row = await db.fetch_one("SELECT affinity_score FROM feed_affinity WHERE feed_id = ?", (feed_id,))
            if feed_row and feed_row['affinity_score'] is not None:
                s_feed = float(feed_row['affinity_score'])

        if starred_counts_map is not None:
            starred_cnt = starred_counts_map.get(feed_id, 0)
            if starred_cnt > 0:
                s_starred_boost = min(1.0, starred_cnt * 0.25)
        else:
            starred_in_feed = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE feed_id = ? AND is_starred = 1", (feed_id,))
            if starred_in_feed and starred_in_feed['c'] > 0:
                s_starred_boost = min(1.0, starred_in_feed['c'] * 0.25)

    score = 0.35 * s_bayes + 0.2 * s_feed + 0.25 * s_freshness + 0.1 * s_explicit + 0.1 * s_starred_boost
    return round(score, 4)


async def _run_rescore_once(db):
    await db.execute("""
        UPDATE articles 
        SET interest_score = 0.0 
        WHERE datetime(published_at) < datetime('now', '-6 months') AND interest_score != 0.0
    """)

    tw_rows = await db.fetch_all("SELECT term, positive_score, negative_score FROM term_weights")
    term_weights_map = {
        r["term"]: (float(r["positive_score"]), float(r["negative_score"]))
        for r in tw_rows
    }

    fa_rows = await db.fetch_all("SELECT feed_id, affinity_score FROM feed_affinity")
    feed_affinity_map = {
        r["feed_id"]: float(r["affinity_score"])
        for r in fa_rows if r.get("affinity_score") is not None
    }

    sc_rows = await db.fetch_all("SELECT feed_id, COUNT(*) as c FROM articles WHERE is_starred = 1 GROUP BY feed_id")
    starred_counts_map = {
        r["feed_id"]: int(r["c"])
        for r in sc_rows if r.get("feed_id") is not None
    }

    articles = await db.fetch_all("""
        SELECT id, feed_id, title, summary, content, published_at, user_vote, is_starred 
        FROM articles 
        WHERE is_read = 0 AND (published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months'))
    """)

    updates: list[tuple[float, int]] = []
    for i, a in enumerate(articles):
        score = await score_article(
            a,
            db,
            term_weights_map=term_weights_map,
            feed_affinity_map=feed_affinity_map,
            starred_counts_map=starred_counts_map,
        )
        updates.append((score, a['id']))
        if (i + 1) % 200 == 0:
            await asyncio.sleep(0)

    batch_size = 500
    update_query = "UPDATE articles SET interest_score = ? WHERE id = ?"
    for start in range(0, len(updates), batch_size):
        batch = updates[start:start + batch_size]
        if hasattr(db, "execute_many"):
            await db.execute_many(update_query, batch)
        elif getattr(db, "_conn", None) is not None:
            await db._conn.executemany(update_query, batch)
            await db._conn.commit()
        else:
            for params in batch:
                await db.execute(update_query, params)
        if start + batch_size < len(updates):
            await asyncio.sleep(0)


async def rescore_articles(db):
    global _rescore_in_progress, _rescore_requested, _rescore_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _rescore_in_progress and _rescore_loop is current_loop:
        _rescore_requested = True
        return

    _rescore_in_progress = True
    _rescore_loop = current_loop
    try:
        while True:
            _rescore_requested = False
            await _run_rescore_once(db)
            if not _rescore_requested:
                break
    finally:
        _rescore_in_progress = False
        _rescore_requested = False
        _rescore_loop = None

async def apply_decay(db):
    await db.execute("UPDATE term_weights SET positive_score = positive_score * 0.985, negative_score = negative_score * 0.985")

