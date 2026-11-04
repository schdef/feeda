import re
import math
from datetime import datetime
from dateutil import parser

STOP_WORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'have', 'from', 'but', 'not',
    'are', 'was', 'were', 'will', 'by', 'der', 'die', 'das', 'und', 'fuer', 'für',
    'mit', 'auf', 'von', 'den', 'dem', 'ein', 'eine', 'einer', 'eines', 'einem',
    'einen', 'ist', 'sind', 'war', 'nicht', 'wie', 'als', 'ueber', 'über',
    'nach', 'bei', 'aus', 'durch', 'oder', 'aber', 'auch', 'zur', 'zum',
    'sich', 'dass'
}

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

    terms = set(extract_terms(article['title'] + " " + (article.get('summary') or "") + " " + (article.get('content') or "")))
    for term in terms:
        if weight > 0:
            await db.execute("""
                INSERT INTO term_weights (term, positive_score) VALUES (?, ?)
                ON CONFLICT(term) DO UPDATE SET positive_score = positive_score + ?, updated_at = CURRENT_TIMESTAMP
            """, (term, weight, weight))
        else:
            w = abs(weight)
            await db.execute("""
                INSERT INTO term_weights (term, negative_score) VALUES (?, ?)
                ON CONFLICT(term) DO UPDATE SET negative_score = negative_score + ?, updated_at = CURRENT_TIMESTAMP
            """, (term, w, w))

async def score_article(article: dict, db) -> float:
    terms = set(extract_terms(article['title'] + " " + (article.get('summary') or "") + " " + (article.get('content') or "")))
    s_bayes = 0.0
    for term in terms:
        row = await db.fetch_one("SELECT positive_score, negative_score FROM term_weights WHERE term = ?", (term,))
        if row:
            s_bayes += (float(row['positive_score']) - float(row['negative_score']))

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
        feed_row = await db.fetch_one("SELECT affinity_score FROM feed_affinity WHERE feed_id = ?", (feed_id,))
        if feed_row and feed_row['affinity_score'] is not None:
            s_feed = float(feed_row['affinity_score'])

        starred_in_feed = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE feed_id = ? AND is_starred = 1", (feed_id,))
        if starred_in_feed and starred_in_feed['c'] > 0:
            s_starred_boost = min(1.0, starred_in_feed['c'] * 0.25)

    score = 0.35 * s_bayes + 0.2 * s_feed + 0.25 * s_freshness + 0.1 * s_explicit + 0.1 * s_starred_boost
    return round(score, 4)

async def rescore_articles(db):
    await db.execute("""
        UPDATE articles 
        SET interest_score = 0.0 
        WHERE datetime(published_at) < datetime('now', '-6 months') AND interest_score != 0.0
    """)
    articles = await db.fetch_all("""
        SELECT id, feed_id, title, summary, content, published_at, user_vote, is_starred 
        FROM articles 
        WHERE is_read = 0 AND (published_at IS NULL OR datetime(published_at) >= datetime('now', '-6 months'))
    """)
    for a in articles:
        score = await score_article(a, db)
        await db.execute("UPDATE articles SET interest_score = ? WHERE id = ?", (score, a['id']))

async def apply_decay(db):
    await db.execute("UPDATE term_weights SET positive_score = positive_score * 0.97, negative_score = negative_score * 0.97")

