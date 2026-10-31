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

    async def close(self):
        if self._conn:
            await self._conn.close()

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

        for filename in sorted(os.listdir(migrations_dir)):
            if filename.endswith(".sql"):
                filepath = os.path.join(migrations_dir, filename)
                with open(filepath, "r") as f:
                    script = f.read()
                await self._conn.executescript(script)
                await self._conn.commit()
                logger.info(f"Ran migration: {filename}")

db = Database()
