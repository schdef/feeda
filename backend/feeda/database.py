import aiosqlite
import os
import logging
from .config import get_settings

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = get_settings().db_path
        self._conn = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        
        await self._conn.execute("PRAGMA busy_timeout = 15000;")
        await self._conn.execute("PRAGMA journal_mode = WAL;")
        await self._conn.execute("PRAGMA synchronous = NORMAL;")
        await self._conn.execute("PRAGMA temp_store = MEMORY;")
        await self._conn.execute("PRAGMA cache_size = -8000;")
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.commit()

        # Schema compatibility check for ai_summary, story_signature, and category columns
        try:
            async with self._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'") as cur:
                table_exists = await cur.fetchone()
            if table_exists:
                async with self._conn.execute("PRAGMA table_info(articles)") as cur:
                    rows = await cur.fetchall()
                    existing_cols = {r[1] for r in rows}
                if "ai_summary" not in existing_cols:
                    await self._conn.execute("ALTER TABLE articles ADD COLUMN ai_summary TEXT;")
                if "story_signature" not in existing_cols:
                    await self._conn.execute("ALTER TABLE articles ADD COLUMN story_signature TEXT;")
                if "category" not in existing_cols:
                    await self._conn.execute("ALTER TABLE articles ADD COLUMN category TEXT DEFAULT NULL;")
                if "category_slug" not in existing_cols:
                    await self._conn.execute("ALTER TABLE articles ADD COLUMN category_slug TEXT DEFAULT NULL;")
                if "category_emoji" not in existing_cols:
                    await self._conn.execute("ALTER TABLE articles ADD COLUMN category_emoji TEXT DEFAULT NULL;")
                await self._conn.commit()
        except Exception as e:
            logger.warning(f"Notice during schema column check: {e}")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: tuple = ()):
        if not self._conn:
            await self.connect()
        async with self._conn.execute(query, params) as cursor:
            await self._conn.commit()
            return cursor.lastrowid

    async def fetch_one(self, query: str, params: tuple = ()):
        if not self._conn:
            await self.connect()
        async with self._conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: tuple = ()):
        if not self._conn:
            await self.connect()
        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def run_migrations(self, migrations_dir: str):
        await self.connect()
        if not os.path.exists(migrations_dir):
            logger.warning(f"Migrations directory {migrations_dir} not found.")
            return

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._conn.commit()

        async with self._conn.execute("SELECT filename FROM _migrations") as cur:
            applied = {r[0] for r in await cur.fetchall()}

        for filename in sorted(os.listdir(migrations_dir)):
            if filename.endswith(".sql"):
                if filename in applied:
                    continue
                filepath = os.path.join(migrations_dir, filename)
                with open(filepath, "r") as f:
                    script = f.read()
                try:
                    await self._conn.executescript(script)
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug(f"Columns in migration {filename} already exist: {e}")
                    else:
                        raise
                await self._conn.execute("INSERT OR IGNORE INTO _migrations (filename) VALUES (?)", (filename,))
                await self._conn.commit()
                logger.info(f"Ran migration: {filename}")

db = Database()
