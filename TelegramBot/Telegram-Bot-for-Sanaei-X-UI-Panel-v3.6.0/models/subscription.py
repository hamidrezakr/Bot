"""
Subscription models for managing user subscriptions and services.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================================
# Enum Models (برای وضعیت‌ها)
# ============================================================

class SubscriptionType:
    """Subscription type constants."""
    BASIC = "basic"
    PREMIUM = "premium"
    BUSINESS = "business"
    TEST = "test"


class SubscriptionStatus:
    """Subscription status constants."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


# ============================================================
# Service Model (برای ذخیره سرویس‌های تعریف شده در پنل)
# ============================================================

class ServiceDB(Base):
    """
    Service database model for storing service configurations.
    
    Attributes:
        id: Unique identifier for the service
        name: Service display name
        category_id: Foreign key to CategoryDB
        panel_id: Foreign key to PanelDB
        inbound_id: Inbound ID from the panel
        volume: Data volume in GB (or "unlimited")
        duration: Duration in months
        users: Number of users allowed (or "unlimited")
        price: Price in Toman
        payment_link: Payment URL for the service
        is_active: Whether the service is active
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    panel_id = Column(Integer, ForeignKey("panels.id"), nullable=True)
    inbound_id = Column(String(50), nullable=True)
    volume = Column(String(20), nullable=True)  # "unlimited" or number
    duration = Column(Integer, nullable=True)   # Months
    users = Column(String(20), nullable=True)   # "unlimited" or number
    price = Column(Integer, nullable=True)      # Toman
    payment_link = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============================================================
# Category Model (برای دسته‌بندی سرویس‌ها)
# ============================================================

class CategoryDB(Base):
    """
    Category database model for grouping services.
    
    Attributes:
        id: Unique identifier for the category
        name: Category display name
        is_active: Whether the category is active
        created_at: Creation timestamp
    """
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


# ============================================================
# Subscription Model (برای اشتراک‌ها)
# ============================================================

class SubscriptionDB(Base):
    """
    Subscription database model for storing user subscriptions.
    
    Attributes:
        id: Unique identifier for the subscription
        user_id: Telegram user ID
        service_id: Foreign key to ServiceDB
        panel_id: Foreign key to PanelDB
        inbound_id: Inbound ID from the panel
        client_email: Email/username of the client in panel
        client_uuid: UUID of the client in panel
        status: Subscription status (pending, active, expired, cancelled)
        type: Subscription type (basic, premium, business, test)
        start_date: Subscription start date
        end_date: Subscription end date
        is_test: Whether this is a test subscription
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # Telegram user ID
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    panel_id = Column(Integer, ForeignKey("panels.id"), nullable=False)
    inbound_id = Column(String(50), nullable=False)
    client_email = Column(String(100), nullable=True)
    client_uuid = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending, active, expired, cancelled
    type = Column(String(20), default="basic")      # basic, premium, business, test
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_test = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============================================================
# Pydantic Models for API
# ============================================================

class Service(BaseModel):
    """Service Pydantic model for API operations."""
    id: Optional[int] = None
    name: str = Field(..., description="Service display name")
    category_id: Optional[int] = Field(None, description="Category ID")
    panel_id: Optional[int] = Field(None, description="Panel ID")
    inbound_id: Optional[str] = Field(None, description="Inbound ID")
    volume: Optional[str] = Field(None, description="Data volume")
    duration: Optional[int] = Field(None, description="Duration in months")
    users: Optional[str] = Field(None, description="Number of users")
    price: Optional[int] = Field(None, description="Price in Toman")
    payment_link: Optional[str] = Field(None, description="Payment URL")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Category(BaseModel):
    """Category Pydantic model for API operations."""
    id: Optional[int] = None
    name: str = Field(..., description="Category display name")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None


class Subscription(BaseModel):
    """
    Subscription Pydantic model for API operations.
    This is the main model used by the bot.
    """
    id: Optional[int] = None
    subscription_id: Optional[str] = Field(None, description="Subscription ID (UUID)")
    user_id: int = Field(..., description="Telegram user ID")
    service_id: Optional[int] = Field(None, description="Service ID")
    panel_id: int = Field(..., description="Panel ID")
    inbound_id: str = Field(..., description="Inbound ID")
    client_email: Optional[str] = Field(None, description="Client email")
    client_uuid: Optional[str] = Field(None, description="Client UUID")
    status: str = Field(default="pending", description="Subscription status")
    type: str = Field(default="basic", description="Subscription type")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_test: bool = Field(default=False)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubscriptionType(str):
    """Subscription type enum for validation."""
    BASIC = "basic"
    PREMIUM = "premium"
    BUSINESS = "business"
    TEST = "test"


class SubscriptionStatus(str):
    """Subscription status enum for validation."""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class ServiceWithDetails(Service):
    """Service with additional details for display."""
    category_name: Optional[str] = None
    panel_name: Optional[str] = None
    panel_url: Optional[str] = None
    panel_sub_url: Optional[str] = None
    inbound_remark: Optional[str] = None


class ReceiptDB(Base):
    """
    Receipt database model for storing payment receipts.
    
    Attributes:
        id: Unique identifier for the receipt
        user_id: Telegram user ID who sent the receipt
        service_id: Service ID being purchased
        service_name: Name of the service
        service_details: Details of the service (volume, duration, price)
        image_path: Path to the uploaded receipt image
        image_filename: Original filename of the image
        status: Status of the receipt (pending, approved, rejected)
        admin_comment: Comment from admin
        created_at: Creation timestamp
        updated_at: Last update timestamp
        processed_at: When the receipt was processed
    """
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    service_id = Column(Integer, nullable=False)
    service_name = Column(String(100), nullable=False)
    service_details = Column(JSON, nullable=True)
    image_path = Column(String(255), nullable=False)
    image_filename = Column(String(255), nullable=True)
    status = Column(String(20), default="pending")  
    admin_comment = Column(String(500), nullable=True)
    admin_message = Column(String(500), nullable=True)  
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    processed_at = Column(DateTime, nullable=True)
    client_email = Column(String(100), nullable=True)
    client_uuid = Column(String(100), nullable=True)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)


class Receipt(BaseModel):
    """Receipt Pydantic model for API operations."""
    id: Optional[int] = None
    user_id: int = Field(..., description="Telegram user ID")
    service_id: int = Field(..., description="Service ID")
    service_name: str = Field(..., description="Service name")
    service_details: Optional[Dict] = Field(None, description="Service details")
    image_path: str = Field(..., description="Path to receipt image")
    image_filename: Optional[str] = Field(None, description="Original filename")
    status: str = Field(default="pending", description="Receipt status")
    admin_comment: Optional[str] = Field(None, description="Admin comment")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
