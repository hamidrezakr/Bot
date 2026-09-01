"""
Settings model for storing application configurations.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SettingsDB(Base):
    """Settings database model."""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserFormatSettings(BaseModel):
    """User format settings model."""
    prefix: str = Field(default="user_", description="Prefix for username")
    start_number: int = Field(default=1000, description="Starting number for sequential usernames")
    use_random_suffix: bool = Field(default=True, description="Whether to add random suffix")
    random_suffix_length: int = Field(default=8, description="Length of random suffix")
    sequential: bool = Field(default=True, description="Whether to use sequential numbering")
