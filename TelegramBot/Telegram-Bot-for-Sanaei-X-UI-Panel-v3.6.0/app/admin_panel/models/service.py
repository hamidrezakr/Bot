"""
Service Model
Stores service plans for sale
"""

from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.sql import func
from core.database import Base


class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    volume = Column(Integer, nullable=False)  # GB
    duration = Column(Integer, nullable=False)  # Days
    price = Column(Integer, nullable=False)  # Toman
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())