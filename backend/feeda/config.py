import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    db_path: str = os.getenv("FEEDA_DB_PATH", "feeda.db")
    host: str = os.getenv("FEEDA_HOST", "0.0.0.0")
    port: int = int(os.getenv("FEEDA_PORT", os.getenv("PORT", "11666")))
    poll_interval_minutes: int = int(os.getenv("FEEDA_POLL_INTERVAL", "30"))
    static_dir: str = os.getenv(
        "FEEDA_STATIC_DIR", 
        os.path.normpath(os.path.join(_BASE_DIR, "../../frontend/dist"))
    )
    plugins_dir: str = os.getenv(
        "FEEDA_PLUGINS_DIR", 
        os.path.join(_BASE_DIR, "plugins")
    )

    model_config = SettingsConfigDict(env_prefix="FEEDA_", extra="ignore")

def get_settings() -> Settings:
    return Settings()
