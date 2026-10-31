from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os

from .database import db
from .config import get_settings
from .routers import feeds, folders, articles, actions, settings, boards
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
    
    app.include_router(settings.router)
    app.include_router(folders.router)
    app.include_router(feeds.router)
    app.include_router(articles.router)
    app.include_router(actions.router)
    app.include_router(boards.router)
    
    s = get_settings()
    if os.path.exists(s.static_dir):
        app.mount("/", StaticFiles(directory=s.static_dir, html=True), name="static")
        
    return app
