import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tests" else Path(__file__).resolve().parent
MIGRATIONS_DIR = str(BASE_DIR / "backend" / "migrations")
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR / "tests"))

from feeda.config import Settings, get_settings
from feeda.database import db
from feeda.app import create_app
from conftest import setup_test_database, teardown_test_database, seed_test_dataset


class TestSecurityHardeningConfig(unittest.TestCase):
    def test_default_config_security_values(self):
        """Verify default host is 127.0.0.1, port is 8000, and api_key is None."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            self.assertEqual(settings.host, "127.0.0.1")
            self.assertEqual(settings.port, 8000)
            self.assertIsNone(settings.api_key)

    def test_api_key_env_override(self):
        """Verify FEEDA_API_KEY is loaded properly."""
        with patch.dict(os.environ, {"FEEDA_API_KEY": "supersecret123"}):
            settings = Settings(_env_file=None)
            self.assertEqual(settings.api_key, "supersecret123")


class TestSecurityApiKeyAuth(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_db, self.db_path = await setup_test_database()
        await seed_test_dataset(self.test_db)

    async def asyncTearDown(self):
        await teardown_test_database(self.test_db, self.db_path)

    async def test_open_access_when_no_api_key(self):
        """When FEEDA_API_KEY is not set, /api/* endpoints are openly accessible."""
        with patch.dict(os.environ, {"FEEDA_API_KEY": ""}):
            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/health")
                self.assertEqual(resp.status_code, 200)

                resp_articles = await client.get("/api/articles")
                self.assertEqual(resp_articles.status_code, 200)

    async def test_auth_enforced_when_api_key_set(self):
        """When FEEDA_API_KEY is set, all /api/* except /api/health require valid key."""
        api_key = "feeda-secret-key-42"
        with patch.dict(os.environ, {"FEEDA_API_KEY": api_key}):
            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Health check is always open
                resp_health = await client.get("/api/health")
                self.assertEqual(resp_health.status_code, 200)

                # 2. Missing key returns 401
                resp_unauth = await client.get("/api/articles")
                self.assertEqual(resp_unauth.status_code, 401)
                self.assertIn("detail", resp_unauth.json())

                # 3. Invalid key returns 401
                resp_bad = await client.get("/api/articles", headers={"Authorization": "Bearer wrong-key"})
                self.assertEqual(resp_bad.status_code, 401)

                # 4. Valid Authorization: Bearer <key>
                resp_bearer = await client.get("/api/articles", headers={"Authorization": f"Bearer {api_key}"})
                self.assertEqual(resp_bearer.status_code, 200)

                # 5. Valid X-API-Key: <key>
                resp_header = await client.get("/api/articles", headers={"X-API-Key": api_key})
                self.assertEqual(resp_header.status_code, 200)

                # 6. Valid ?token=<key>
                resp_query = await client.get(f"/api/articles?token={api_key}")
                self.assertEqual(resp_query.status_code, 200)

                # 7. Other /api/* endpoints are also protected
                resp_stats_unauth = await client.get("/api/stats")
                self.assertEqual(resp_stats_unauth.status_code, 401)

                resp_stats_auth = await client.get("/api/stats", headers={"X-API-Key": api_key})
                self.assertEqual(resp_stats_auth.status_code, 200)


class TestFTSSearchSanitization(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_db, self.db_path = await setup_test_database()
        await seed_test_dataset(self.test_db)
        app = create_app()
        self.transport = ASGITransport(app=app)

    async def asyncTearDown(self):
        await teardown_test_database(self.test_db, self.db_path)

    async def test_special_characters_do_not_crash_search(self):
        """Verify queries with special characters do not trigger SQLite FTS syntax errors."""
        edge_queries = [
            '"unmatched quote',
            '"""',
            'foo:bar',
            'python:3',
            '*+*',
            'c++',
            'test*',
            'AND',
            'OR',
            'NOT',
            'AND OR NOT',
            'NEAR(a, b)',
            ':::',
            '   ',
            '',
            'technology AND AI',
            'special !@#$%^&*()_+ query'
        ]
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            for q in edge_queries:
                resp = await client.get(f"/api/articles/search?q={q}")
                self.assertEqual(
                    resp.status_code, 200,
                    f"FTS search failed with query {q!r}: {resp.status_code} {resp.text}"
                )
                data = resp.json()
                self.assertIn("articles", data)
                self.assertIn("total", data)
                self.assertIsInstance(data["articles"], list)
