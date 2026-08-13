"""
Configuration management using Pydantic Settings.
All environment variables are loaded from .env file.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Telegram Bot
    bot_token: str
    
    # X-UI Panel (for future use)
    xui_url: Optional[str] = None
    xui_username: Optional[str] = None
    xui_password: Optional[str] = None
    xui_inbound_id: int = 2
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Webhook
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create a global settings instance
settings = Settings()


# For backward compatibility
BOT_TOKEN = settings.bot_token