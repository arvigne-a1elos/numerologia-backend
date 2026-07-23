"""Configuration management for the application."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Stripe Configuration
    stripe_secret_key: str = ""
    
    # Email Configuration
    from_email: str = "arvigne@gmail.com"
    from_name: str = "Mapa Numerologico"
    
    # API Configuration
    base_url: str = "https://numerologia-api-wd2q.onrender.com"
    allowed_origins: list[str] = ["*"]  # Change to specific origins in production
    
    # Database Configuration
    database_url: str = "sqlite:///./numerologia.db"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
