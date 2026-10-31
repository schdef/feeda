-- Folders for organizing feeds
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RSS Feed subscriptions
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    site_url TEXT,
    favicon_url TEXT,
    description TEXT,
    etag TEXT,
    last_modified TEXT,
    poll_interval_minutes INTEGER DEFAULT 30,
    last_polled_at TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Story clusters for deduplication grouping
CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    primary_article_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Articles
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    cluster_id INTEGER REFERENCES clusters(id) ON DELETE SET NULL,
    guid TEXT,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    summary TEXT,
    content TEXT,
    image_url TEXT,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title_shingles TEXT,
    content_simhash INTEGER,
    is_read INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0,
    user_vote INTEGER DEFAULT 0,
    read_at TIMESTAMP,
    interest_score REAL DEFAULT 0,
    UNIQUE(feed_id, url_hash)
);

-- FTS5 full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title,
    summary,
    content,
    content='articles',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- FTS triggers
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, new.content);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, content)
    VALUES('delete', old.id, old.title, old.summary, old.content);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, content)
    VALUES('delete', old.id, old.title, old.summary, old.content);
    INSERT INTO articles_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, new.content);
END;

-- Interactions log
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    dwell_time_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Term weights for Naive Bayes
CREATE TABLE IF NOT EXISTS term_weights (
    term TEXT PRIMARY KEY,
    positive_score REAL DEFAULT 0,
    negative_score REAL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feed affinity
CREATE TABLE IF NOT EXISTS feed_affinity (
    feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,
    articles_received INTEGER DEFAULT 0,
    articles_read INTEGER DEFAULT 0,
    affinity_score REAL DEFAULT 0.5
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_articles_simhash ON articles(content_simhash);
CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(interest_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read);
CREATE INDEX IF NOT EXISTS idx_articles_starred ON articles(is_starred);
CREATE INDEX IF NOT EXISTS idx_interactions_article ON interactions(article_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at DESC);
