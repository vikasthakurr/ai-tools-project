"""
Application configuration — loads from environment variables via Pydantic.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Required
    gemini_api_key: str = ""

    # Optional
    promptlayer_api_key: Optional[str] = None
    database_path: str = "./ecommerce.db"
    environment: str = "development"
    port: int = 8000

    # Prompt settings
    active_prompt_version: int = 3
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0
    gemini_max_tokens: int = 500

    # Rate limiting
    rate_limit_per_minute: int = 10

    # Logging
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def promptlayer_enabled(self) -> bool:
        return self.promptlayer_api_key is not None and self.promptlayer_api_key != ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
