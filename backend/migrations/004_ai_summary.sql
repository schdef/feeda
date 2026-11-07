-- Migration 004: Add AI summary and story signature columns and indexes
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_story_sig ON articles(story_signature);
CREATE INDEX IF NOT EXISTS idx_articles_pub_fetch ON articles(published_at, fetched_at);
