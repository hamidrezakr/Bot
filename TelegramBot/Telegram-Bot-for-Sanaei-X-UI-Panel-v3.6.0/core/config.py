"""
Configuration management module for the Telegram bot.
Handles environment variables and application settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import pytz 
# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # API Base URL for internal communication
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    
    # Admin Authentication
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "secret_key_for_session")

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///telegram_bot.db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Application Settings
    APP_NAME: str = "Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server Settings (optional)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"
    
    # Timezone
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tehran")

    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields to be ignored
        extra = "ignore"


# Create global settings instance
settings = Settings()


def validate_settings() -> None:
    """
    Validate required settings.
    
    Raises:
        ValueError: If required settings are missing.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    if not settings.TELEGRAM_WEBHOOK_URL:
        raise ValueError("TELEGRAM_WEBHOOK_URL is required")

def get_timezone():
    """Get timezone object."""
    return pytz.timezone(settings.TIMEZONE)
