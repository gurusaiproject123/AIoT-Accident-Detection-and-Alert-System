"""Application settings loaded from environment variables or backend/.env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # pragma: no cover - optional if python-dotenv is absent
    pass


class Settings(BaseModel):
    """Runtime configuration for the AIoT Accident Detection backend."""

    app_name: str = "AIoT Accident Detection API"
    app_version: str = "0.1.0"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # CORS origins for React dev servers
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # Supabase / PostgreSQL connection
    supabase_url: str = Field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_publishable_key: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    )
    supabase_service_role_key: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Agreed workflow timers from the Backend Development Guide
    cancellation_window_seconds: int = Field(
        default_factory=lambda: int(os.getenv("CANCELLATION_WINDOW_SECONDS", "30"))
    )
    hospital_ack_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("HOSPITAL_ACK_TIMEOUT_SECONDS", "180"))
    )
    max_escalation_level: int = Field(
        default_factory=lambda: int(os.getenv("MAX_ESCALATION_LEVEL", "3"))
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: SecretStr

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
    return Settings()
