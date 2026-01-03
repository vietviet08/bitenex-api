# =============================================================================
# Core Configuration Module
# =============================================================================
# This module centralizes all application settings using Pydantic Settings.
# All configuration is loaded from environment variables with sensible defaults.
# 
# Architectural Intent:
# - Single source of truth for all configuration
# - Type-safe configuration with validation
# - Environment-based configuration (12-factor app)
# =============================================================================

from functools import lru_cache
from typing import List

from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic-settings for automatic env loading and validation.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_name: str = "Bitenex API"
    app_env: str = "development"  # development | staging | production
    debug: bool = True
    api_version: str = "v1"
    secret_key: str = "change-this-in-production"

    # -------------------------------------------------------------------------
    # Database Settings (PostgreSQL + AsyncPG)
    # -------------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/bitenex"
    database_echo: bool = False  # SQL query logging

    # -------------------------------------------------------------------------
    # Redis Settings
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # -------------------------------------------------------------------------
    # JWT Authentication Settings
    # -------------------------------------------------------------------------
    jwt_secret_key: str = "jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # -------------------------------------------------------------------------
    # CORS Settings
    # -------------------------------------------------------------------------
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # -------------------------------------------------------------------------
    # WebSocket Settings
    # -------------------------------------------------------------------------
    ws_message_queue_size: int = 100

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON-like string from env
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Handle comma-separated string
                return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Using lru_cache ensures settings are only loaded once.
    """
    return Settings()


# Export singleton for convenience
settings = get_settings()
