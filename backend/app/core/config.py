# LaTablée backend config (12-factor via pydantic-settings)
# All values overridable with LATABLEE_ prefixed env vars or a dotenv file
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LATABLEE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "LaTablée"
    version: str = "0.4.3"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Database: SQLite by default; Postgres via compose profile (see docker-compose.yml)
    database_url: str = "sqlite:///./data/latablee.db"

    # Auth
    secret_key: str = "CHANGE-ME-in-production-see-README"  # env LATABLEE_SECRET_KEY overrides
    access_token_expire_minutes: int = 60 * 24 * 14  # 14 days
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536  # 64 MiB
    argon2_parallelism: int = 2

    # CORS — comma-separated origins, no wildcard by default
    cors_origins: str = "http://localhost:3000"

    # Household timezone (IANA name) — set during onboarding, changeable in settings
    household_timezone: str = "UTC"

    # Optional LLM (any OpenAI-compatible endpoint). Empty base URL = AI features off.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_vision_model: str = ""  # falls back to llm_model

    # Frontend origin (for invite links)
    public_origin: str = "http://localhost:3000"

    # Max upload sizes (bytes)
    max_upload_bytes: int = 15 * 1024 * 1024


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings


def reload_settings() -> Settings:
    """Re-read env (used by tests)."""
    global _settings
    _settings = None
    return get_settings()


DATA_DIR = Path("data")
IMAGES_DIR = DATA_DIR / "images"
EXPORTS_DIR = DATA_DIR / "exports"

# Single-container mode: directory containing the built web UI (Next.js static export).
# Empty/unset → UI not served by the API (two-container nginx mode).
STATIC_DIR: Path | None = Path(os.getenv("LATABLEE_STATIC_DIR", "")).resolve() if os.getenv("LATABLEE_STATIC_DIR", "").strip() else None


def ensure_dirs() -> None:
    for d in (DATA_DIR, IMAGES_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
