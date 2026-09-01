"""
Panel model for managing X-UI panels.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PanelDB(Base):
    """
    Panel database model for storing panel configurations.
    
    Attributes:
        id: Unique identifier for the panel
        name: Display name of the panel
        url: Base URL of the X-UI panel
        api_token: API authentication token
        sub_url: Subscription URL for clients
        inbound_ids: List of inbound IDs selected for this panel
        status: Current health status (running, stopped, unknown)
        version: X-UI panel version
        total_sent: Total sent traffic in bytes
        total_recv: Total received traffic in bytes
        users_count: Number of active users
        is_active: Whether the panel is active
        created_at: Creation timestamp
        updated_at: Last update timestamp
        last_check: Last health check timestamp
    """
    __tablename__ = "panels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)
    api_token = Column(String(255), nullable=False)
    sub_url = Column(String(255), nullable=True)
    inbound_ids = Column(JSON, default=[])
    status = Column(String(20), default="unknown")
    version = Column(String(20), nullable=True)
    total_sent = Column(BigInteger, default=0)
    total_recv = Column(BigInteger, default=0)
    users_count = Column(Integer, default=0)
    capacity = Column(Integer, default=0)  
    is_full = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_check = Column(DateTime, nullable=True)


class Panel(BaseModel):
    """
    Panel Pydantic model for API operations.
    """
    id: Optional[int] = None
    name: str = Field(..., description="Panel display name")
    url: str = Field(..., description="Panel base URL")
    api_token: str = Field(..., description="API authentication token")
    sub_url: Optional[str] = Field(None, description="Subscription URL")
    inbound_ids: List[str] = Field(default=[], description="Selected inbound IDs")
    status: str = Field(default="unknown", description="Panel health status")
    version: Optional[str] = Field(None, description="X-UI panel version")
    total_sent: int = Field(default=0, description="Total sent traffic in bytes")
    total_recv: int = Field(default=0, description="Total received traffic in bytes")
    users_count: int = Field(default=0, description="Number of active users")
    capacity: int = Field(default=0, description="Maximum users allowed (0 = unlimited)")
    is_full: bool = Field(default=False, description="Whether panel is at full capacity")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_check: Optional[datetime] = None

class PanelStatus(BaseModel):
    """
    Panel status response model.
    """
    status: str = Field(..., description="Panel health status")
    version: str = Field(..., description="X-UI panel version")
    users_count: int = Field(..., description="Number of active users")
    capacity: int = Field(..., description="Maximum users allowed")
    is_full: bool = Field(..., description="Whether panel is full")
    total_sent: int = Field(..., description="Total sent traffic in bytes")
    total_recv: int = Field(..., description="Total received traffic in bytes")
    last_check: datetime = Field(default_factory=datetime.now)


class InboundInfo(BaseModel):
    """
    Inbound information model.
    """
    id: int = Field(..., description="Inbound ID")
    remark: str = Field(..., description="Inbound remark/name")
    port: Optional[int] = Field(None, description="Inbound port")
    protocol: Optional[str] = Field(None, description="Inbound protocol")
    clients_count: int = Field(default=0, description="Number of clients in this inbound")
    active_clients: int = Field(default=0, description="Number of active clients")
