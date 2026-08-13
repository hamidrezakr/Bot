"""
Payment Link Model
Stores payment links for each panel and service
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class PaymentLink(Base):
    __tablename__ = "payment_links"
    
    id = Column(Integer, primary_key=True, index=True)
    panel_id = Column(Integer, ForeignKey("panels.id"))
    service_id = Column(Integer, ForeignKey("services.id"))
    link = Column(String(500), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    panel = relationship("Panel")
    service = relationship("Service")