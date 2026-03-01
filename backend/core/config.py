"""
Application configuration using Pydantic Settings.
All environment variables are loaded and validated here.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ElevenLabs
    elevenlabs_api_key: str = ""

    # Google Places
    google_places_api_key: str = ""

    # NVIDIA NIM (Mistral)
    nvidia_api_key: str = ""

    # Mistral API (Devstral for agentic VibeCoder)
    mistral_api_key: str = ""

    # Composio (Gmail integration)
    composio_api_key: str = ""

    # W&B Weave
    wandb_api_key: str = ""
    weave_project: str = "friendly-blitz"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # App
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    demo_mode: bool = False

    # Rate limiting
    rate_limit_per_minute: int = 10

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list, ensuring proper URL format."""
        origins = []
        for origin in self.cors_origins.split(","):
            origin = origin.strip()
            if not origin:
                continue
            # Auto-add https:// if missing protocol
            if not origin.startswith("http://") and not origin.startswith("https://"):
                origin = f"https://{origin}"
            origins.append(origin)
        return origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
