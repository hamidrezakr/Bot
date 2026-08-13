"""
Panel Model
Stores X-UI panel configurations
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from core.database import Base


class Panel(Base):
    __tablename__ = "panels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)
    token = Column(String(255), nullable=False)
    status = Column(String(20), default="active")
    user_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Pydantic models for API
from pydantic import BaseModel


class PanelCreate(BaseModel):
    name: str
    url: str
    token: str
    status: str = "active"


class PanelUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    token: Optional[str] = None
    status: Optional[str] = None