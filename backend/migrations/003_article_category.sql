-- Migration 003: Add category columns to articles
ALTER TABLE articles ADD COLUMN category TEXT DEFAULT NULL;
ALTER TABLE articles ADD COLUMN category_slug TEXT DEFAULT NULL;
ALTER TABLE articles ADD COLUMN category_emoji TEXT DEFAULT NULL;
