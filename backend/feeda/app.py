from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import os
import hmac

from .database import db
from .config import get_settings
from .routers import feeds, folders, articles, actions, settings, boards, analytics
from .services.feed_poller import feed_poller_task
from .services.plugin_manager import discover_plugins

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    base_dir = os.path.dirname(os.path.abspath(__file__))
    migrations_dir = os.path.normpath(os.path.join(base_dir, "../migrations"))
    if not os.path.exists(migrations_dir):
        migrations_dir = "migrations"
    await db.run_migrations(migrations_dir)
    discover_plugins(get_settings().plugins_dir)
    from .services.seeder import seed_database
    await seed_database()
    from .services.ranker import prune_stop_words_from_term_weights
    await prune_stop_words_from_term_weights(db)
    from .services.interest_grouper import backfill_article_categories
    await backfill_article_categories(db)
    asyncio.create_task(feed_poller_task())
    yield
    # Shutdown
    await db.close()

def create_app() -> FastAPI:
    app = FastAPI(title="Feeda", version="0.1.0", lifespan=lifespan)
    
    app.add_middleware(
        CORSMiddleware, 
        allow_origins=["*"], 
        allow_credentials=True, 
        allow_methods=["*"], 
        allow_headers=["*"]
    )

    @app.middleware("http")
    async def api_key_auth_middleware(request: Request, call_next):
        settings = get_settings()
        api_key = settings.api_key
        
        # If API key is configured, protect /api/* except /api/health
        if api_key and request.url.path.startswith("/api"):
            if request.url.path not in ("/api/health", "/api/health/"):
                if request.method != "OPTIONS":
                    token = None
                    auth_header = request.headers.get("Authorization")
                    if auth_header:
                        parts = auth_header.split()
                        if len(parts) == 2 and parts[0].lower() == "bearer":
                            token = parts[1]
                        elif len(parts) == 1:
                            token = parts[0]
                    if not token:
                        token = request.headers.get("X-API-Key")
                    if not token:
                        token = request.query_params.get("token")
                    
                    if not token or not hmac.compare_digest(token, api_key):
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Unauthorized: Invalid or missing API key"}
                        )
        
        return await call_next(request)
    
    app.include_router(settings.router)
    app.include_router(folders.router)
    app.include_router(feeds.router)
    app.include_router(articles.router)
    app.include_router(actions.router)
    app.include_router(boards.router)
    app.include_router(analytics.router)
    
    s = get_settings()
    if os.path.exists(s.static_dir):
        app.mount("/", StaticFiles(directory=s.static_dir, html=True), name="static")
        
    return app
