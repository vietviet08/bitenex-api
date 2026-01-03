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

from pydantic import field_validator
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
    APP_NAME: str = "Bitenex API"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = True
    API_VERSION: str = "v1"
    SECRET_KEY: str = "change-this-in-production"
    
    # -------------------------------------------------------------------------
    # Database Settings (PostgreSQL + AsyncPG)
    # -------------------------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/bitenex"
    DATABASE_ECHO: bool = False  # SQL query logging
    
    # -------------------------------------------------------------------------
    # Redis Settings
    # -------------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # -------------------------------------------------------------------------
    # JWT Authentication Settings
    # -------------------------------------------------------------------------
    JWT_SECRET_KEY: str = "jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # -------------------------------------------------------------------------
    # CORS Settings
    # -------------------------------------------------------------------------
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # -------------------------------------------------------------------------
    # WebSocket Settings
    # -------------------------------------------------------------------------
    WS_MESSAGE_QUEUE_SIZE: int = 100
    
    @field_validator("CORS_ORIGINS", mode="before")
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
