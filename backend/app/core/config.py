"""Application settings loaded from environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the AIoT Accident Detection backend."""

    app_name: str = "AIoT Accident Detection API"
    app_version: str = "0.1.0"
    environment: str = "development"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    supabase_url: str
    supabase_publishable_key: str = ""
    supabase_service_role_key: SecretStr
    database_url: str = ""

    cancellation_window_seconds: int = 30
    hospital_ack_timeout_seconds: int = 180
    max_escalation_level: int = 3

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
