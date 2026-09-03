from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Executive Assistant"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_executive_assistant"

    # Default application timezone used for "today" / overdue calculations.
    # Must not be hard-coded as UTC anywhere business logic runs.
    app_timezone: str = "Asia/Almaty"

    cors_origins: list[str] = ["*"]

    # Sprint 2 — Voice Note AI Capture (PRD §20). "fake" is the deterministic,
    # network-free default used in CI and local dev without credentials.
    stt_provider: str = "fake"
    stt_base_url: str | None = None
    stt_api_key: str | None = None
    stt_model: str | None = None

    llm_provider: str = "fake"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    voice_capture_max_seconds: int = 90
    voice_capture_max_bytes: int = 15 * 1024 * 1024
    voice_capture_ttl_hours: int = 24
    voice_capture_max_retries: int = 3
    # Local filesystem directory for opaque audio storage keys (PRD §23).
    # Not part of the PRD's required env-var list; internal to this MVP's
    # storage adapter and swappable without touching callers.
    voice_capture_storage_dir: str = "./.voice_audio"

    ai_request_timeout_seconds: int = 30
    ai_max_retries: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
