from functools import lru_cache
from typing import List, cast

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
    app_name: str = "Bitenex"
    app_env: str = "dev"  # dev | stg | prod
    debug: bool = True
    api_version: str = "v1"
    secret_key: str = "change-this-in-production"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bitenex"
    database_echo: bool = True

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    ws_message_queue_size: int = 100

    internal_api_token: str = "dev-internal-token"

    # n8n integration
    n8n_base_url: str = "http://localhost:5678"
    n8n_webhook_secret: str = "change-this-n8n-secret"
    n8n_webhook_enabled: bool = True

    # Firebase Cloud Messaging
    firebase_project_id: str | None = None
    firebase_credentials_path: str | None = None
    firebase_credentials_json: str | None = None

    # VNPAY (sandbox by default)
    vnp_tmn_code: str
    vnp_hash_secret: str
    vnp_url: str
    vnp_return_url: str
    vnp_ipn_url: str

    # SMTP Settings
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_tls_ssl: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON-like string from env
            import json

            try:
                parsed = json.loads(v)
                return cast(List[str], parsed)
            except json.JSONDecodeError:
                # Handle comma-separated string
                return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Using lru_cache ensures settings are only loaded once.
    """
    return Settings()
