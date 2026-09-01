"""
User model for the Telegram bot.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """
    User model representing a Telegram user.
    """
    user_id: int = Field(..., description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    first_name: str = Field(..., description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    created_at: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    is_active: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123456789,
                "username": "john_doe",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": True
            }
        }


class UserStatus(BaseModel):
    """
    User status response model.
    """
    user_id: int
    username: Optional[str]
    status: str = Field(..., description="User status: active, inactive, suspended")
    subscription_expiry: Optional[datetime] = None
    subscription_type: Optional[str] = None
    remaining_days: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123456789,
                "username": "john_doe",
                "status": "active",
                "subscription_expiry": "2024-12-31T23:59:59",
                "subscription_type": "premium",
                "remaining_days": 30
            }
        }
