# admin/routes/admin_routes.py
"""
Admin panel routes for the Telegram bot.
Provides web interface for managing panels, services, users, and settings.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import httpx
import json
import re
import secrets
import string
from core.logging import logger
from services.user_service import UserService
from services.subscription_service import SubscriptionService
from core.config import settings

# ==============================================
# Database Setup
# ==============================================
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, JSON, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# Initialize services
user_service = UserService()
subscription_service = SubscriptionService()

# ==============================================
# Database Setup for Panels
# ==============================================
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class PanelDB(Base):
    """Panel database model."""
    __tablename__ = "panels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)
    api_token = Column(String(255), nullable=False)
    sub_url = Column(String(255), nullable=True)
    inbound_ids = Column(JSON, default=[])
    inbound_details = Column(JSON, default=[])
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
    """Panel Pydantic model for API."""
    id: Optional[int] = None
    name: str = Field(..., description="Panel name")
    url: str = Field(..., description="Panel URL")
    api_token: str = Field(..., description="API token")
    inbound_ids: List[str] = Field(default=[], description="List of inbound IDs")
    status: str = Field(default="unknown", description="Panel status")
    users_count: int = Field(default=0, description="Number of active users")
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_check: Optional[datetime] = None

# ==============================================
# Database Setup for Categories  
# ==============================================
class CategoryDB(Base):
    """Category database model."""
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


# ==============================================
# Database Setup for Services  
# ==============================================
class ServiceDB(Base):
    """Service database model."""
    __tablename__ = "services"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, nullable=True)
    panel_id = Column(Integer, nullable=True)
    inbound_id = Column(String(50), nullable=True)
    volume = Column(String(20), nullable=True)
    duration = Column(Integer, nullable=True)
    users = Column(String(20), nullable=True)
    price = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ==============================================
# Database Setup for Receipts
# ==============================================

class ReceiptDB(Base):
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
    is_renewal = Column(Boolean, default=False)
    renew_user_info = Column(JSON, nullable=True)

# ==============================================
# Database Setup for Settings
# ==============================================

class SettingsDB(Base):
    """Settings database model."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ==============================================
# Database Setup for Test Account Settings
# ==============================================

class TestAccountSettingsDB(Base):
    """Test account settings database model."""
    __tablename__ = "test_account_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=True)
    volume_mb = Column(Integer, default=100)
    duration_days = Column(Integer, default=1)
    max_per_week = Column(Integer, default=2)
    limit_days = Column(Integer, default=7)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TestAccountDB(Base):
    """Test account history database model."""
    __tablename__ = "test_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    panel_id = Column(Integer, nullable=False)
    panel_name = Column(String(100), nullable=True)
    client_email = Column(String(100), nullable=False)
    client_sub_id = Column(String(100), nullable=True)
    volume_mb = Column(Integer, default=100)
    duration_days = Column(Integer, default=1)
    expiry_time = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.now)


# ==============================================
# Payment Settings Model
# ==============================================

class PaymentSettingsDB(Base):
    """Payment settings database model."""
    __tablename__ = "payment_settings"

    id = Column(Integer, primary_key=True, index=True)
    online_payment_enabled = Column(Boolean, default=False)
    receipt_payment_enabled = Column(Boolean, default=True)
    merchant_id = Column(String(100), nullable=True)
    sandbox_mode = Column(Boolean, default=True)  
    card_numbers = Column(JSON, default=[])
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# ==============================================
# User Database Model
# ==============================================

class UserDB(Base):
    """User database model for storing Telegram users."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PaymentDB(Base):
    """Payment database model."""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    service_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    authority = Column(String(100), nullable=False, unique=True)
    ref_id = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  
    payment_type = Column(String(20), default="new_purchase")  
    is_renewal = Column(Boolean, default=False)
    renew_user_info = Column(JSON, nullable=True)
    client_email = Column(String(100), nullable=True)
    client_sub_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    paid_at = Column(DateTime, nullable=True)

# ==============================================
# Referral Settings Model
# ==============================================

class ReferralSettingsDB(Base):
    """Referral settings database model."""
    __tablename__ = "referral_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=True)
    first_purchase_discount = Column(Integer, default=10)  
    recurring_discount = Column(Integer, default=5)  
    min_redeem_percent = Column(Integer, default=100)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ReferralDB(Base):
    """Referral database model."""
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, nullable=False, index=True)  
    referred_id = Column(Integer, nullable=False, index=True) 
    discount_percent = Column(Integer, default=10)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class ReferralDiscountDB(Base):
    """Referral discount credit database model."""
    __tablename__ = "referral_discounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    total_percent = Column(Integer, default=0)
    used_percent = Column(Integer, default=0)
    remaining_percent = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)



class ChannelSettingsDB(Base):
    """Channel settings database model."""
    __tablename__ = "channel_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_username = Column(String(100), nullable=True)  # @channel_name
    channel_chat_id = Column(String(100), nullable=True)
    channel_url = Column(String(255), nullable=True)  # https://t.me/channel_name
    is_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# ==============================================
# Sales Partner Models
# ==============================================

class SalesPartnerDB(Base):
    """Sales partner database model."""
    __tablename__ = "sales_partners"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    max_purchases = Column(Integer, default=10)
    used_purchases = Column(Integer, default=0)
    discount_percent = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class SalesTransactionDB(Base):
    """Sales transaction database model."""
    __tablename__ = "sales_transactions"

    id = Column(Integer, primary_key=True, index=True)
    partner_user_id = Column(Integer, nullable=False, index=True)
    client_email = Column(String(100), nullable=False)
    service_id = Column(Integer, nullable=True)
    service_name = Column(String(100), nullable=True)
    price = Column(Integer, default=0)
    original_price = Column(Integer, default=0)
    discount_percent = Column(Integer, default=0)
    transaction_type = Column(String(20), default="purchase")  # purchase / renewal
    is_settled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class SalesRequestDB(Base):
    """Sales partner request database model."""
    __tablename__ = "sales_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, default=datetime.now)

# ==============================================
# Message Settings Model
# ==============================================

class MessageSettingsDB(Base):
    """Message settings database model."""
    __tablename__ = "message_settings"

    id = Column(Integer, primary_key=True, index=True)
    welcome_message = Column(Text, nullable=True)
    support_message = Column(Text, nullable=True)
    help_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# ==============================================
# Helper Functions for User Generation
# ==============================================
# ==============================================
# Gift Account Models
# ==============================================

class GiftAccountSettingsDB(Base):
    """Gift account settings database model."""
    __tablename__ = "gift_account_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=False)
    panel_ids = Column(JSON, default=[])
    volume_gb = Column(Integer, default=10)
    duration_days = Column(Integer, default=1)
    limit_ip = Column(Integer, default=0)
    schedule_hour = Column(Integer, default=12)
    schedule_minute = Column(Integer, default=0)
    post_duration_minutes = Column(Integer, default=30)
    post_message = Column(Text, nullable=True)
    current_panel_index = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GiftAccountDB(Base):
    """Gift account history database model."""
    __tablename__ = "gift_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    client_email = Column(String(100), nullable=False)
    client_sub_id = Column(String(100), nullable=True)
    panel_id = Column(Integer, nullable=True)
    panel_name = Column(String(100), nullable=True)
    channel_message_id = Column(BigInteger, nullable=True)
    volume_gb = Column(Integer, default=10)
    duration_days = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)


async def get_user_format_settings_helper() -> dict:
    """
    Get user format settings from database.

    Returns:
        dict: User format settings with default values if not found
    """
    try:
        db = SessionLocal()
        setting = db.query(SettingsDB).filter(SettingsDB.key == "user_format").first()
        db.close()

        if setting:
            return setting.value
        return {
            "prefix": "user_",
            "start_number": 1000,
            "sequential": True,
            "use_random_suffix": True,
            "random_suffix_length": 8
        }
    except Exception as e:
        logger.error(f"Error getting user format settings: {str(e)}")
        return {
            "prefix": "user_",
            "start_number": 1000,
            "sequential": True,
            "use_random_suffix": True,
            "random_suffix_length": 8
        }


async def get_last_user_number() -> int:
    """
    Get the last used number from settings or receipts.
    
    Returns:
        int: Last used number or default start number
    """
    try:
        db = SessionLocal()
        setting = db.query(SettingsDB).filter(SettingsDB.key == "last_user_number").first()
        if setting:
            db.close()
            return setting.value
        
        last_receipt = db.query(ReceiptDB).filter(
            ReceiptDB.client_email.isnot(None)
        ).order_by(ReceiptDB.id.desc()).first()
        db.close()
        
        if last_receipt and last_receipt.client_email:
            match = re.search(r'user_(\d+)_', last_receipt.client_email)
            if match:
                return int(match.group(1))
        
        return 1000
    except Exception as e:
        logger.error(f"Error getting last user number: {str(e)}")
        return 1000

async def update_last_user_number(number: int) -> None:
    """
    Update the last user number in settings.

    Args:
        number: The number to save
    """
    try:
        db = SessionLocal()
        setting = db.query(SettingsDB).filter(SettingsDB.key == "last_user_number").first()
        if setting:
            setting.value = number
            setting.updated_at = datetime.now()
        else:
            setting = SettingsDB(key="last_user_number", value=number)
            db.add(setting)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Error updating last user number: {str(e)}")

async def generate_username(user_id: int) -> str:
    """
    Generate a username based on settings.
    
    Args:
        user_id: Telegram user ID (unused but kept for consistency)
    
    Returns:
        str: Generated username
    """
    settings = await get_user_format_settings_helper()
    prefix = settings.get("prefix", "user_")
    
    # ====== دریافت آخرین شماره و افزایش ======
    last_number = await get_last_user_number()
    next_number = last_number + 1
    
    # ====== ساخت نام کاربری ======
    username = f"{prefix}{next_number}"
    
    if settings.get("use_random_suffix", True):
        length = settings.get("random_suffix_length", 8)
        suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length))
        username = f"{username}_{suffix}"
    
    # ====== ذخیره شماره جدید ======
    await update_last_user_number(next_number)
    
    return username

# ==============================================
# API ENDPOINTS FOR RECEIPTS
# ==============================================

@router.get("/api/receipts")
async def get_receipts(archived: bool = False):
    """
    Get all receipts.
    If archived=True, return archived receipts only.
    """
    try:
        db = SessionLocal()
        query = db.query(ReceiptDB).filter(ReceiptDB.is_archived == archived)
        receipts = query.order_by(ReceiptDB.created_at.desc()).all()
        db.close()

        result = []
        for r in receipts:
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "username": r.username or "نامشخص",
                "service_id": r.service_id,
                "service_name": r.service_name,
                "service_details": r.service_details or {},
                "image_path": r.image_path,
                "image_filename": r.image_filename,
                "status": r.status,
                "admin_comment": r.admin_comment,
                "admin_message": r.admin_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                "client_email": r.client_email,
                "client_uuid": r.client_uuid
            })

        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting receipts: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.put("/api/receipts/{receipt_id}")
async def update_receipt(receipt_id: int, request: Request):
    """Update receipt status and admin message."""
    try:
        data = await request.json()
        db = SessionLocal()

        receipt = db.query(ReceiptDB).filter(ReceiptDB.id == receipt_id).first()
        if not receipt:
            db.close()
            return {"status": "error", "message": "رسید پیدا نشد"}

        if "status" in data:
            receipt.status = data["status"]
        if "admin_comment" in data:
            receipt.admin_comment = data["admin_comment"]
        if "admin_message" in data:
            receipt.admin_message = data["admin_message"]  
        if data.get("status") in ["approved", "rejected"]:
            receipt.processed_at = datetime.now()
            receipt.is_archived = True
            receipt.archived_at = datetime.now()

        receipt.updated_at = datetime.now()
        db.commit()
        
        receipt_id = receipt.id
        receipt_status = receipt.status
        receipt_admin_message = receipt.admin_message
        
        db.close()

        if receipt_admin_message and receipt.user_id:
            await send_message_to_user(receipt.user_id, receipt_admin_message)
        elif receipt.user_id:
            if receipt_status == "approved":
                default_message = "✅ رسید شما تأیید شد. اکانت شما ساخته شده است."
            else:
                default_message = "❌ رسید شما رد شد. لطفاً با پشتیبانی تماس بگیرید."
            await send_message_to_user(receipt.user_id, default_message)

        logger.info(f"Receipt {receipt_id} updated to {receipt_status}")
        return {"status": "success", "message": "رسید با موفقیت بروزرسانی شد"}
    except Exception as e:
        logger.error(f"Error updating receipt: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/receipts/{receipt_id}/archive")
async def archive_receipt(receipt_id: int):
    """Archive a receipt manually."""
    try:
        db = SessionLocal()
        receipt = db.query(ReceiptDB).filter(ReceiptDB.id == receipt_id).first()
        if not receipt:
            db.close()
            return {"status": "error", "message": "رسید پیدا نشد"}

        receipt.is_archived = True
        receipt.archived_at = datetime.now()
        db.commit()
        db.close()

        return {"status": "success", "message": "رسید با موفقیت آرشیو شد"}
    except Exception as e:
        logger.error(f"Error archiving receipt: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# Helper function to send message to user
# ==============================================

async def send_message_to_user(user_id: int, message: str):
    """Send a message to a Telegram user."""
    try:
        from api.routes.webhook import application
        await application.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown"
        )
        logger.info(f"Message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {str(e)}")



# Create tables if not exists
def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(engine)


init_db()


def get_pending_receipts_count() -> int:
    """Get count of pending receipts for badge."""
    # In production, fetch from database
    return 3


# ==============================================
# PAGE ROUTES
# ==============================================

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """
    Admin dashboard page with statistics and charts.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered dashboard template
    """
    logger.info("Admin dashboard accessed")

    context = {
        "request": request,
        "active": "dashboard",
        "total_users": 1247,
        "active_services": 892,
        "active_services_percent": 71.5,
        "today_revenue": 1845000,
        "today_revenue_growth": 12.3,
        "pending_receipts": get_pending_receipts_count(),
        "recent_activities": [
            {"color": "green", "icon": "✅", "text": "کاربر جدید ثبت نام کرد: علی رضایی", "time": "۵ دقیقه پیش"},
            {"color": "blue", "icon": "🛒", "text": "خرید جدید: 30GB - 1 ماه", "time": "۱۲ دقیقه پیش"},
            {"color": "yellow", "icon": "💰", "text": "رسید جدید نیاز به تأیید", "time": "۳۰ دقیقه پیش"},
            {"color": "purple", "icon": "📡", "text": "پنل جدید اضافه شد: پنل اروپا", "time": "۱ ساعت پیش"},
            {"color": "pink", "icon": "🔄", "text": "تمدید سرویس: 50GB - 2 ماه", "time": "۲ ساعت پیش"},
        ],
        "monthly_sales": [120000, 150000, 200000, 180000, 250000, 300000, 280000]
    }

    return templates.TemplateResponse("dashboard.html", context)


@router.get("/panels", response_class=HTMLResponse)
async def admin_panels(request: Request):
    """
    Admin panels management page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered panels template
    """
    logger.info("Admin panels page accessed")

    context = {
        "request": request,
        "active": "panels",
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("panels.html", context)


@router.get("/categories", response_class=HTMLResponse)
async def admin_categories(request: Request):
    """
    Admin categories management page.
    """
    logger.info("Admin categories page accessed")
    context = {
        "request": request,
        "active": "categories",
        "pending_receipts": get_pending_receipts_count()
    }
    return templates.TemplateResponse("categories.html", context)


@router.get("/services", response_class=HTMLResponse)
async def admin_services(request: Request):
    """
    Admin services management page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered services template
    """
    logger.info("Admin services page accessed")

    context = {
        "request": request,
        "active": "services",
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("services.html", context)


@router.get("/receipts", response_class=HTMLResponse)
async def admin_receipts(request: Request):
    """
    Admin receipts management page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered receipts template
    """
    logger.info("Admin receipts page accessed")

    context = {
        "request": request,
        "active": "receipts",
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("receipts.html", context)


@router.get("/reports", response_class=HTMLResponse)
async def admin_reports(request: Request):
    """
    Admin reports page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered reports template
    """
    logger.info("Admin reports page accessed")

    context = {
        "request": request,
        "active": "reports",
        "total_revenue": 15240000,
        "total_transactions": 1247,
        "avg_transaction": 12280,
        "growth_rate": 18.5,
        "weekly_sales": [50, 80, 120, 95],
        "service_distribution": [30, 25, 20, 15, 7, 3],
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("reports.html", context)


@router.get("/staff", response_class=HTMLResponse)
async def admin_staff(request: Request):
    """
    Admin staff management page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered staff template
    """
    logger.info("Admin staff page accessed")

    context = {
        "request": request,
        "active": "staff",
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("staff.html", context)


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """
    Admin settings page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Rendered settings template
    """
    logger.info("Admin settings page accessed")

    context = {
        "request": request,
        "active": "settings",
        "pending_receipts": get_pending_receipts_count()
    }

    return templates.TemplateResponse("settings.html", context)

# ==============================================
# API ENDPOINTS FOR CATEGORIES
# ==============================================

@router.get("/api/categories")
async def get_categories():
    """Get all categories."""
    try:
        db = SessionLocal()
        categories = db.query(CategoryDB).all()
        db.close()
        result = [{"id": c.id, "name": c.name, "created_at": c.created_at.isoformat() if c.created_at else None} for c in categories]
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting categories: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/categories")
async def create_category(request: Request):
    """Create a new category."""
    try:
        data = await request.json()
        name = data.get("name", "").strip()
        if not name:
            return {"status": "error", "message": "نام دسته‌بندی الزامی است"}
        
        db = SessionLocal()
        existing = db.query(CategoryDB).filter(CategoryDB.name == name).first()
        if existing:
            db.close()
            return {"status": "error", "message": "این دسته‌بندی قبلاً ثبت شده است"}
        
        new_category = CategoryDB(name=name)
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        db.close()
        
        logger.info(f"Category created: {new_category.name} (ID: {new_category.id})")
        return {"status": "success", "message": "دسته‌بندی با موفقیت اضافه شد", "data": {"id": new_category.id, "name": new_category.name}}
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.delete("/api/categories/{category_id}")
async def delete_category(category_id: int):
    """Delete a category."""
    try:
        db = SessionLocal()
        category = db.query(CategoryDB).filter(CategoryDB.id == category_id).first()
        if not category:
            db.close()
            return {"status": "error", "message": "دسته‌بندی پیدا نشد"}
        db.delete(category)
        db.commit()
        db.close()
        logger.info(f"Category deleted: ID {category_id}")
        return {"status": "success", "message": "دسته‌بندی با موفقیت حذف شد"}
    except Exception as e:
        logger.error(f"Error deleting category: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# API ENDPOINTS FOR PANELS
# ==============================================

@router.get("/api/panels")
async def get_panels():
    """
    Get all panels with detailed information including status.
    """
    try:
        db = SessionLocal()
        panels = db.query(PanelDB).all()
        db.close()

        result = []
        for p in panels:
            result.append({
                "id": p.id,
                "name": p.name,
                "url": p.url,
                "sub_url": p.sub_url,
                "api_token": p.api_token,  # ✅ تغییر: توکن کامل
                "inbound_ids": p.inbound_ids or [],
                "inbound_details": p.inbound_details or [],
                "status": p.status,
                "version": p.version,
                "users_count": p.users_count,
                "total_sent": p.total_sent,
                "total_recv": p.total_recv,
                "capacity": p.capacity,
                "is_full": p.is_full,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                "last_check": p.last_check.isoformat() if p.last_check else None
            })

        return {"status": "success", "data": result}

    except Exception as e:
        logger.error(f"Error getting panels: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/panels")
async def create_panel(request: Request):
    """
    Create a new panel with validation and initial configuration.
    """
    try:
        data = await request.json()

        # Validate required fields
        required_fields = ["name", "url", "api_token"]
        for field in required_fields:
            if not data.get(field):
                return {"status": "error", "message": f"فیلد {field} الزامی است"}

        db = SessionLocal()

        # Check if panel with same name exists
        existing = db.query(PanelDB).filter(PanelDB.name == data.get("name")).first()
        if existing:
            db.close()
            return {"status": "error", "message": "پنل با این نام قبلاً ثبت شده است"}

        # Get capacity
        capacity = data.get("capacity", 0)
        if capacity is None:
            capacity = 0
        elif isinstance(capacity, str):
            capacity = 0 if capacity.lower() == "unlimited" else int(capacity) if capacity else 0

        # ====== مهم: دریافت inbound_details ======
        inbound_details = data.get("inbound_details", [])

        # ====== اگر inbound_details خالی است اما inbound_ids پر است، از inbound_ids استفاده کن ======
        if not inbound_details and data.get("inbound_ids"):
            for inbound_id in data.get("inbound_ids", []):
                inbound_details.append({
                    "id": inbound_id,
                    "remark": "",
                    "port": None,
                    "protocol": "",
                    "active_clients": 0
                })

        # ====== چاپ لاگ برای دیباگ ======
        logger.info(f"Creating panel with inbound_details: {inbound_details}")

        new_panel = PanelDB(
            name=data.get("name"),
            url=data.get("url").rstrip("/"),
            api_token=data.get("api_token"),
            sub_url=data.get("sub_url"),
            inbound_ids=data.get("inbound_ids", []),
            inbound_details=inbound_details,  
            status="unknown",
            users_count=0,
            capacity=capacity,
            is_full=False,
            is_active=True
        )

        db.add(new_panel)
        db.commit()
        db.refresh(new_panel)
        db.close()

        logger.info(f"Panel created: {new_panel.name} (ID: {new_panel.id})")

        return {
            "status": "success",
            "message": "پنل با موفقیت اضافه شد",
            "data": {
                "id": new_panel.id,
                "name": new_panel.name,
                "url": new_panel.url,
                "sub_url": new_panel.sub_url,
                "inbound_ids": new_panel.inbound_ids,
                "inbound_details": new_panel.inbound_details,
                "status": new_panel.status,
                "users_count": new_panel.users_count,
                "capacity": new_panel.capacity,
                "is_full": new_panel.is_full
            }
        }

    except Exception as e:
        logger.error(f"Error creating panel: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.put("/api/panels/{panel_id}")
async def update_panel(panel_id: int, request: Request):
    """
    Update an existing panel with new configuration.
    """
    try:
        data = await request.json()
        db = SessionLocal()
        
        panel = db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        # Update fields
        if "name" in data:
            panel.name = data["name"]
        if "url" in data:
            panel.url = data["url"].rstrip("/")
        if "api_token" in data:
            panel.api_token = data["api_token"]
        if "sub_url" in data:
            panel.sub_url = data["sub_url"]
        if "inbound_ids" in data:
            panel.inbound_ids = data["inbound_ids"]
        if "inbound_details" in data:
            panel.inbound_details = data["inbound_details"]
        if "capacity" in data:
            capacity = data["capacity"]
            if capacity is None or capacity == "" or capacity == "unlimited":
                panel.capacity = 0
            else:
                panel.capacity = int(capacity)
        if "is_active" in data:
            panel.is_active = data["is_active"]
        
        # Update is_full based on capacity and users_count
        if panel.capacity > 0:
            panel.is_full = panel.users_count >= panel.capacity
        else:
            panel.is_full = False
        
        panel.updated_at = datetime.now()
        
        db.commit()
        db.refresh(panel)
        db.close()
        
        logger.info(f"Panel updated: {panel.name} (ID: {panel.id})")
        
        return {
            "status": "success",
            "message": "پنل با موفقیت ویرایش شد",
            "data": {
                "id": panel.id,
                "name": panel.name,
                "url": panel.url,
                "sub_url": panel.sub_url,
                "inbound_ids": panel.inbound_ids,
                "inbound_details": panel.inbound_details,
                "status": panel.status,
                "users_count": panel.users_count,
                "capacity": panel.capacity,
                "is_full": panel.is_full
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating panel: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.delete("/api/panels/{panel_id}")
async def delete_panel(panel_id: int):
    """
    Delete a panel from the system.
    
    Args:
        panel_id: Panel ID
    
    Returns:
        Status message
    """
    try:
        db = SessionLocal()
        
        panel = db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        db.delete(panel)
        db.commit()
        db.close()
        
        logger.info(f"Panel deleted: ID {panel_id}")
        
        return {
            "status": "success",
            "message": "پنل با موفقیت حذف شد"
        }
        
    except Exception as e:
        logger.error(f"Error deleting panel: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/panels/{panel_id}/check-status")
async def check_panel_status(panel_id: int):
    """
    Check panel health status and update all panel information.
    Fetches: status, version, traffic, users, inbounds.
    """
    try:
        db = SessionLocal()
        panel = db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        url = panel.url.rstrip("/")
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel.api_token}"
        }
        
        status_data = {}
        clients_data = []
        
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            # 1. Get server status
            try:
                resp = await client.get(f"{url}/panel/api/server/status", headers=headers)
                if resp.status_code == 200:
                    status_data = resp.json()
                    logger.info(f"Status response: {status_data}")
            except Exception as e:
                logger.warning(f"Could not fetch status: {str(e)}")
            
            # 2. Get inbounds and clients
            try:
                resp = await client.get(f"{url}/panel/api/inbounds/list", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and data.get("obj"):
                        for inbound in data.get("obj", []):
                            clients = inbound.get("clientStats", [])
                            for client in clients:
                                if client.get("enable"):
                                    clients_data.append(client)
            except Exception as e:
                logger.warning(f"Could not fetch clients: {str(e)}")
        
        # ====== اصلاح وضعیت ======
        # بررسی وضعیت از پاسخ API
        state = status_data.get("state", "").lower()
        
        if state == "running":
            panel.status = "running"
        elif state == "stopped":
            panel.status = "stopped"
        elif state == "offline":
            panel.status = "offline"
        else:
            # اگر پنل پاسخ داد، ولی state مشخص نبود، سالم در نظر بگیر
            if status_data:
                panel.status = "running"
            else:
                panel.status = "unknown"
        
        panel.version = status_data.get("panelVersion")
        panel.total_sent = status_data.get("netTraffic", {}).get("sent", 0)
        panel.total_recv = status_data.get("netTraffic", {}).get("recv", 0)
        panel.users_count = len(clients_data)
        panel.last_check = datetime.now()
        
        # بروزرسانی ظرفیت
        if panel.capacity > 0:
            panel.is_full = panel.users_count >= panel.capacity
        else:
            panel.is_full = False
        
        db.commit()
        db.refresh(panel)
        db.close()
        
        return {
            "status": "success",
            "data": {
                "panel_status": panel.status,
                "version": panel.version,
                "users_count": panel.users_count,
                "capacity": panel.capacity,
                "is_full": panel.is_full,
                "total_sent": panel.total_sent,
                "total_recv": panel.total_recv,
                "last_check": panel.last_check.isoformat(),
                "inbound_ids": panel.inbound_ids or []
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking panel status: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/panels/fetch-inbounds")
async def fetch_inbounds(request: Request):
    """
    Fetch inbound list from a panel for preview.
    Used during panel creation to show available inbounds.
    
    Returns:
        List of inbounds with id, remark, port, protocol
    """
    try:
        data = await request.json()
        url = data.get("url")
        token = data.get("api_token")
        
        if not url or not token:
            return {"status": "error", "message": "آدرس URL و توکن API الزامی است"}
        
        # ====== اصلاح: حذف / اضافی از انتهای آدرس ======
        url = url.rstrip("/")
        
        full_url = f"{url}/panel/api/inbounds/list"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        logger.info(f"Fetching inbounds from: {full_url}")
        
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            response = await client.get(full_url, headers=headers)
            
            # ====== اگر خطای 404 بود، پیام مناسب برگردان ======
            if response.status_code == 404:
                logger.warning(f"Inbounds endpoint not found: {full_url}")
                return {"status": "error", "message": "آدرس پنل یا توکن صحیح نیست - مسیر Inbound‌ها پیدا نشد (404)"}
            
            response.raise_for_status()
            data = response.json()
            
            inbounds = []
            if data.get("success") and data.get("obj"):
                for inbound in data.get("obj", []):
                    clients = inbound.get("clientStats", [])
                    active_clients = len([c for c in clients if c.get("enable")])
                    
                    inbounds.append({
                        "id": inbound.get("id"),
                        "remark": inbound.get("remark", ""),
                        "port": inbound.get("port"),
                        "protocol": inbound.get("protocol"),
                        "enable": inbound.get("enable", False),
                        "clients_count": len(clients),
                        "active_clients": active_clients
                    })
            
            return {
                "status": "success",
                "data": {
                    "inbounds": inbounds,
                    "total": len(inbounds)
                }
            }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching inbounds: {str(e)}")
        return {"status": "error", "message": f"خطا در ارتباط با پنل: {e.response.status_code}"}
    except httpx.ConnectError:
        return {"status": "error", "message": "اتصال به پنل ناموفق - سرور در دسترس نیست"}
    except httpx.TimeoutException:
        return {"status": "error", "message": "زمان ارتباط با پنل به پایان رسید"}
    except Exception as e:
        logger.error(f"Error fetching inbounds: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/panels/fetch-clients")
async def fetch_clients(request: Request):
    """
    Fetch clients list from a panel.
    
    Args:
        request: FastAPI request with panel URL and token
    
    Returns:
        List of clients
    """
    try:
        data = await request.json()
        url = data.get("url")
        token = data.get("api_token")
        
        if not url or not token:
            return {"status": "error", "message": "آدرس URL و توکن API الزامی است"}
        
        url = url.rstrip("/")
        full_url = f"{url}/panel/api/inbounds/list"  # Use inbounds list to get all clients
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            response = await client.get(full_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Count all active clients across all inbounds
            total_clients = 0
            total_active = 0
            clients_list = []
            
            if data.get("success") and data.get("obj"):
                for inbound in data.get("obj", []):
                    clients = inbound.get("clientStats", [])
                    for client in clients:
                        clients_list.append({
                            "email": client.get("email"),
                            "enable": client.get("enable", False),
                            "inbound_id": inbound.get("id"),
                            "inbound_remark": inbound.get("remark", "")
                        })
                        total_clients += 1
                        if client.get("enable"):
                            total_active += 1
            
            return {
                "status": "success",
                "data": {
                    "clients": clients_list,
                    "total": total_clients,
                    "active": total_active
                }
            }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching clients: {str(e)}")
        return {"status": "error", "message": f"خطا در ارتباط با پنل: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Error fetching clients: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# API ENDPOINTS FOR SERVICES
# ==============================================

@router.get("/api/services")
async def get_services():
    """Get all services."""
    try:
        db = SessionLocal()
        services = db.query(ServiceDB).all()
        result = []
        for s in services:
            # Get category name
            category_name = None
            if s.category_id:
                cat = db.query(CategoryDB).filter(CategoryDB.id == s.category_id).first()
                if cat:
                    category_name = cat.name

            # Get panel name
            panel_name = None
            if s.panel_id:
                panel = db.query(PanelDB).filter(PanelDB.id == s.panel_id).first()
                if panel:
                    panel_name = panel.name

            result.append({
                "id": s.id,
                "name": s.name,
                "category_id": s.category_id,
                "category_name": category_name,
                "panel_id": s.panel_id,
                "panel_name": panel_name,
                "inbound_id": s.inbound_id,
                "volume": s.volume,
                "duration": s.duration,
                "users": s.users,
                "price": s.price,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None
            })
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting services: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/services")
async def create_service(request: Request):
    """Create a new service."""
    try:
        data = await request.json()

        # Validation
        if not data.get("name"):
            return {"status": "error", "message": "نام سرویس الزامی است"}

        db = SessionLocal()

        new_service = ServiceDB(
            name=data.get("name"),
            category_id=data.get("category_id"),
            panel_id=data.get("panel_id"),
            inbound_id=data.get("inbound_id"),
            volume=data.get("volume"),
            duration=data.get("duration"),
            users=data.get("users"),
            price=data.get("price"),
            is_active=True
        )

        db.add(new_service)
        db.commit()
        db.refresh(new_service)
        db.close()

        logger.info(f"Service created: {new_service.name} (ID: {new_service.id})")
        return {"status": "success", "message": "سرویس با موفقیت اضافه شد", "data": {"id": new_service.id}}
    except Exception as e:
        logger.error(f"Error creating service: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.put("/api/services/{service_id}")
async def update_service(service_id: int, request: Request):
    """Update an existing service."""
    try:
        data = await request.json()
        db = SessionLocal()

        service = db.query(ServiceDB).filter(ServiceDB.id == service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}

        # Update fields
        if "name" in data:
            service.name = data["name"]
        if "category_id" in data:
            service.category_id = data["category_id"]
        if "panel_id" in data:
            service.panel_id = data["panel_id"]
        if "inbound_id" in data:
            service.inbound_id = data["inbound_id"]
        if "volume" in data:
            service.volume = data["volume"]
        if "duration" in data:
            service.duration = data["duration"]
        if "users" in data:
            service.users = data["users"]
        if "price" in data:
            service.price = data["price"]
        if "is_active" in data:
            service.is_active = data["is_active"]

        service.updated_at = datetime.now()
        
        db.commit()
        
        service_id = service.id
        service_name = service.name
        
        db.close()

        logger.info(f"Service updated: {service_name} (ID: {service_id})")
        return {"status": "success", "message": "سرویس با موفقیت ویرایش شد"}
        
    except Exception as e:
        logger.error(f"Error updating service: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.delete("/api/services/{service_id}")
async def delete_service(service_id: int):
    """Delete a service."""
    try:
        db = SessionLocal()
        service = db.query(ServiceDB).filter(ServiceDB.id == service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}
        db.delete(service)
        db.commit()
        db.close()
        logger.info(f"Service deleted: ID {service_id}")
        return {"status": "success", "message": "سرویس با موفقیت حذف شد"}
    except Exception as e:
        logger.error(f"Error deleting service: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# WEBHOOK ROUTES
# ==============================================

@router.post("/reset-webhook")
async def reset_webhook():
    """
    Reset the Telegram webhook.

    Returns:
        dict: Status message
    """
    try:
        from api.routes.webhook import delete_webhook, set_webhook

        # Delete existing webhook
        await delete_webhook()

        # Set new webhook
        await set_webhook()

        logger.info("Webhook reset via admin panel")
        return {"status": "success", "message": "Webhook reset successfully"}

    except Exception as e:
        logger.error(f"Error resetting webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# API ENDPOINTS FOR BOT (Public)
# ==============================================

@router.get("/api/public/categories")
async def get_public_categories():
    """
    Get all categories for bot.
    This endpoint is public and used by the Telegram bot.
    """
    try:
        db = SessionLocal()
        categories = db.query(CategoryDB).filter(
            CategoryDB.is_active == True
        ).all()
        db.close()

        result = [{"id": c.id, "name": c.name} for c in categories]
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting public categories: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/public/services")
async def get_public_services(category_id: int = None):
    """
    Get services for bot.
    If category_id is provided, filter by category.
    """
    try:
        db = SessionLocal()

        query = db.query(ServiceDB).filter(ServiceDB.is_active == True)
        if category_id:
            query = query.filter(ServiceDB.category_id == category_id)

        services = query.all()

        result = []
        for s in services:
            # Get panel info
            panel_name = None
            if s.panel_id:
                panel = db.query(PanelDB).filter(PanelDB.id == s.panel_id).first()
                if panel:
                    panel_name = panel.name

            result.append({
                "id": s.id,
                "name": s.name,
                "category_id": s.category_id,
                "panel_id": s.panel_id,
                "panel_name": panel_name,
                "inbound_id": s.inbound_id,
                "volume": s.volume,
                "duration": s.duration,
                "users": s.users,
                "price": s.price
            })

        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting public services: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/public/panel/{panel_id}")
async def get_public_panel(panel_id: int):
    """
    Get panel details for bot.
    """
    try:
        db = SessionLocal()
        panel = db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}

        result = {
            "id": panel.id,
            "name": panel.name,
            "url": panel.url,
            "sub_url": panel.sub_url,
            "inbound_details": panel.inbound_details or [],
            "capacity": panel.capacity,
            "is_full": panel.is_full,
            "users_count": panel.users_count
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting public panel: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# API ENDPOINTS FOR RECEIPTS (اضافه کردن POST)
# ==============================================

@router.post("/api/receipts")
async def create_receipt(request: Request):
    """Create a new receipt."""
    try:
        data = await request.json()

        required_fields = ["user_id", "service_id", "service_name", "image_path"]
        for field in required_fields:
            if not data.get(field):
                return {"status": "error", "message": f"فیلد {field} الزامی است"}

        db = SessionLocal()

        new_receipt = ReceiptDB(
            user_id=data.get("user_id"),
            username=data.get("username"),
            service_id=data.get("service_id"),
            service_name=data.get("service_name"),
            service_details=data.get("service_details", {}),
            image_path=data.get("image_path"),
            image_filename=data.get("image_filename"),
            status="pending",
            is_renewal=data.get("is_renewal", False),
            renew_user_info=data.get("renew_user_info")  # ← اضافه شد
        )

        db.add(new_receipt)
        db.commit()
        db.refresh(new_receipt)
        db.close()

        logger.info(f"Receipt created for user {data.get('user_id')} (ID: {new_receipt.id}, renewal: {data.get('is_renewal', False)})")
        return {"status": "success", "message": "رسید با موفقیت ذخیره شد", "data": {"id": new_receipt.id}}
    except Exception as e:
        logger.error(f"Error creating receipt: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/receipts/{receipt_id}/approve")
async def approve_receipt(receipt_id: int):
    """
    Approve a receipt and create/renew user in panel.
    """
    db = None
    try:
        db = SessionLocal()
        receipt = db.query(ReceiptDB).filter(ReceiptDB.id == receipt_id).first()
        if not receipt:
            if db:
                db.close()
            return {"status": "error", "message": "رسید پیدا نشد"}

        is_renewal = getattr(receipt, 'is_renewal', False)
        logger.info(f"Processing receipt {receipt_id} - is_renewal: {is_renewal}")

        # ====== ذخیره اطلاعات receipt قبل از بستن سشن ======
        receipt_user_id = receipt.user_id
        receipt_service_id = receipt.service_id
        receipt_username = receipt.username or "کاربر"

        if is_renewal:
            # ============================================================
            # RENEWAL PROCESS
            # ============================================================
            renew_user_info = getattr(receipt, 'renew_user_info', None)
            logger.info(f"Renew user info: {renew_user_info}")

            if not renew_user_info:
                db.close()
                return {"status": "error", "message": "اطلاعات کاربر برای تمدید یافت نشد"}

            service = db.query(ServiceDB).filter(ServiceDB.id == receipt_service_id).first()
            if not service:
                db.close()
                return {"status": "error", "message": "سرویس پیدا نشد"}

            panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
            if not panel:
                db.close()
                return {"status": "error", "message": "پنل پیدا نشد"}

            username = renew_user_info.get('email')
            client_data = renew_user_info.get('client', {})

            # ====== ذخیره اطلاعات panel قبل از بستن سشن ======
            panel_url = panel.url.rstrip("/")
            panel_api_token = panel.api_token
            panel_sub_url = panel.sub_url or ""
            panel_name = panel.name

            if not username:
                db.close()
                return {"status": "error", "message": "نام کاربری برای تمدید یافت نشد"}

            logger.info(f"Renewing user: {username} in panel: {panel_name}")

            # ====== محاسبه زمان باقی‌مانده ======
            current_expiry_time = client_data.get('expiryTime', 0)
            remaining_days = 0

            if current_expiry_time and current_expiry_time > 0:
                current_expiry_date = datetime.fromtimestamp(current_expiry_time / 1000)
                remaining_days = (current_expiry_date - datetime.now()).days
                if remaining_days < 0:
                    remaining_days = 0

            # ====== محاسبه زمان جدید ======
            duration_months = service.duration or 1
            new_days = duration_months * 30
            total_days = remaining_days + new_days

            # ====== محاسبه تاریخ انقضای جدید ======
            new_expiry_time = int((datetime.now() + timedelta(days=total_days)).timestamp() * 1000)
            new_expiry_date = datetime.now() + timedelta(days=total_days)

            # ====== محاسبه حجم باقی‌مانده ======
            current_total_bytes = client_data.get('totalGB', 0)
            current_used_bytes = client_data.get('usedGB', 0)
            
            if current_used_bytes == 0:
                current_used_bytes = client_data.get('usedTraffic', 0)
            
            if current_total_bytes > 0:
                remaining_bytes = max(0, current_total_bytes - current_used_bytes)
                
                service_volume = service.volume
                if service_volume and service_volume != "unlimited":
                    try:
                        new_volume_bytes = int(service_volume) * 1073741824
                    except:
                        new_volume_bytes = 0
                else:
                    new_volume_bytes = 0
                
                new_total_bytes = remaining_bytes + new_volume_bytes
            else:
                remaining_bytes = 0
                new_volume_bytes = 0
                new_total_bytes = 0

            # ====== آماده‌سازی داده برای بروزرسانی ======
            update_data = {
                "email": username,
                "totalGB": new_total_bytes,
                "expiryTime": new_expiry_time,
                "tgId": client_data.get('tgId', receipt_user_id),
                "limitIp": client_data.get('limitIp', 0),
                "enable": True,
                "subId": client_data.get('subId', '')
            }

            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {panel_api_token}",
                "Content-Type": "application/json"
            }

            # ====== ارسال درخواست به پنل ======
            async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                update_resp = await http_client.post(
                    f"{panel_url}/panel/api/clients/update/{username}",
                    headers=headers,
                    json=update_data
                )

                if update_resp.status_code != 200:
                    db.close()
                    return {"status": "error", "message": f"خطا در تمدید سرویس: {update_resp.text}"}

                result = update_resp.json()
                if not result.get("success"):
                    db.close()
                    return {"status": "error", "message": result.get("msg", "خطا در تمدید")}

            # ====== ذخیره در دیتابیس ======
            receipt.status = "approved"
            receipt.processed_at = datetime.now()
            receipt.is_archived = True
            receipt.archived_at = datetime.now()
            db.commit()
            db.close()

            # ====== ✅ Apply recurring discount for referrer ======
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    recurring_response = await client.post(
                        f"http://localhost:8000/admin/api/referrals/apply-recurring",
                        json={"user_id": receipt_user_id}
                    )
                    recurring_result = recurring_response.json()
                    logger.info(f"Recurring discount applied: {recurring_result}")
            except Exception as e:
                logger.error(f"Error applying recurring discount: {str(e)}")

            # ====== ارسال پیام موفقیت به کاربر ======
            client_sub_id = client_data.get('subId', '')
            full_sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else panel_sub_url

            if current_total_bytes > 0:
                volume_message = (
                    f"📊 **حجم:**\n"
                    f"   قبلی: {current_total_bytes/1073741824:.1f} GB\n"
                    f"   مصرفی: {current_used_bytes/1073741824:.1f} GB\n"
                    f"   باقی‌مانده: {remaining_bytes/1073741824:.1f} GB\n"
                    f"   جدید اضافه شده: {new_volume_bytes/1073741824:.1f} GB\n"
                    f"   کل جدید: {new_total_bytes/1073741824:.1f} GB"
                )
            else:
                volume_message = "📊 **حجم:** ♾️ نامحدود"

            await send_message_to_user(
                receipt_user_id,
                f"✅ **سرویس شما با موفقیت تمدید شد!**\n\n"
                f"📧 **یوزرنیم:** `{username}`\n"
                f"{volume_message}\n\n"
                f"📅 **مدت باقی‌مانده قبلی:** {remaining_days} روز\n"
                f"📅 **مدت جدید اضافه‌شده:** {new_days} روز\n"
                f"📅 **مدت کل:** {total_days} روز\n"
                f"📅 **تاریخ انقضای جدید:** {new_expiry_date.strftime('%Y-%m-%d')}\n\n"
                f"🔗 **لینک سابسکریپشن:**\n{full_sub_url}\n\n"
                f"💡 برای مشاهده اطلاعات جدید از بخش 'وضعیت من' استفاده کنید."
            )

            return {
                "status": "success",
                "message": "سرویس با موفقیت تمدید شد",
                "data": {
                    "username": username,
                    "renewed": True,
                    "sub_url": full_sub_url,
                    "remaining_days": remaining_days,
                    "added_days": new_days,
                    "total_days": total_days,
                    "new_expiry": new_expiry_date.isoformat(),
                    "volume": {
                        "old_total_gb": current_total_bytes/1073741824,
                        "used_gb": current_used_bytes/1073741824,
                        "remaining_gb": remaining_bytes/1073741824,
                        "added_gb": new_volume_bytes/1073741824,
                        "new_total_gb": new_total_bytes/1073741824
                    }
                }
            }

        else:
            # ============================================================
            # NORMAL PURCHASE PROCESS
            # ============================================================
            service = db.query(ServiceDB).filter(ServiceDB.id == receipt_service_id).first()
            if not service:
                db.close()
                return {"status": "error", "message": "سرویس پیدا نشد"}

            panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
            if not panel:
                db.close()
                return {"status": "error", "message": "پنل پیدا نشد"}

            panel_url = panel.url.rstrip("/")
            panel_api_token = panel.api_token
            panel_sub_url = panel.sub_url or ""
            panel_name = panel.name
            service_name = service.name
            service_volume = service.volume
            service_duration = service.duration
            service_inbound_id = service.inbound_id
            service_price = service.price

            logger.info(f"✅ Creating new user - Panel: {panel_name}, Service: {service_name}")

            # ====== ساخت نام کاربری ======
            email = await generate_username(receipt_user_id)

            # ====== محاسبه حجم ======
            if service_volume and service_volume != "unlimited":
                try:
                    totalGB = int(service_volume) * 1073741824
                except:
                    totalGB = 0
            else:
                totalGB = 0

            # ====== محاسبه تاریخ انقضا ======
            duration_months = service_duration or 1
            expiry_time = int((datetime.now() + timedelta(days=duration_months * 30)).timestamp() * 1000)
            expiry_date = datetime.now() + timedelta(days=duration_months * 30)

            limit_ip = 3 if totalGB == 0 else 0

            # ====== دریافت Inbound IDs ======
            inbound_ids = []
            if service_inbound_id:
                try:
                    inbound_ids = [int(service_inbound_id)]
                except:
                    inbound_ids = []

            if not inbound_ids:
                db.close()
                return {"status": "error", "message": "هیچ Inboundی برای این سرویس تعریف نشده است"}

            # ====== ساخت subId ======
            import uuid
            client_sub_id = str(uuid.uuid4())

            # ====== آماده‌سازی داده کاربر ======
            client_data = {
                "client": {
                    "email": email,
                    "totalGB": totalGB,
                    "expiryTime": expiry_time,
                    "tgId": receipt_user_id,
                    "limitIp": limit_ip,
                    "enable": True,
                    "subId": client_sub_id
                },
                "inboundIds": inbound_ids
            }

            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {panel_api_token}",
                "Content-Type": "application/json"
            }

            # ====== ارسال درخواست به پنل ======
            async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                response = await http_client.post(
                    f"{panel_url}/panel/api/clients/add",
                    headers=headers,
                    json=client_data
                )

                if response.status_code != 200:
                    db.close()
                    return {"status": "error", "message": f"خطا در ساخت کاربر: {response.text}"}

                result = response.json()
                if not result.get("success"):
                    db.close()
                    return {"status": "error", "message": result.get("msg", "خطا در ساخت کاربر")}

            # ====== ذخیره در دیتابیس ======
            receipt.status = "approved"
            receipt.processed_at = datetime.now()
            receipt.client_email = email
            receipt.client_sub_id = client_sub_id
            receipt.is_archived = True
            receipt.archived_at = datetime.now()
            db.commit()
            db.close()

            # ====== ✅ Apply referral discount (first purchase) and recurring ======
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Apply first purchase referral discount
                    await client.post(
                        f"http://localhost:8000/admin/api/referrals/apply",
                        json={"user_id": receipt_user_id}
                    )
                    # Apply recurring discount for referrer
                    await client.post(
                        f"http://localhost:8000/admin/api/referrals/apply-recurring",
                        json={"user_id": receipt_user_id}
                    )
            except Exception as e:
                logger.error(f"Error applying referral discounts: {str(e)}")

            # ====== ارسال پیام موفقیت به کاربر ======
            full_sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else panel_sub_url
            volume_display = service_volume if service_volume else "نامحدود"

            message_lines = [
                "✅ **پرداخت شما تأیید شد!**",
                "",
                f"📧 **یوزرنیم:** `{email}`",
                f"📦 **حجم:** {volume_display} GB",
                f"⏰ **مدت اعتبار:** {duration_months} روز",
                "",
                f"🔗 **لینک سابسکریپشن:** ",
                f"{full_sub_url}",
                "",
                "📱 **نحوه استفاده:**",
                "لینک سابسکریپشن را در اپلیکیشن خود وارد کنید.",
                "",
                "📖 **راهنمای نصب:** ",
                "https://t.me/SpaceGateVPN/705",
                "",
                "⚠️ **لطفاً یوزرنیم خود را برای استفاده از دستور \"وضعیت من\" ذخیره کنید.**"
            ]
            message = "\n".join(message_lines)

            await send_message_to_user(receipt_user_id, message)

            return {
                "status": "success",
                "message": "رسید تأیید شد و کاربر در پنل ساخته شد",
                "data": {
                    "client_email": email,
                    "client_sub_id": client_sub_id,
                    "sub_url": full_sub_url,
                    "panel_url": panel_url
                }
            }

    except Exception as e:
        logger.error(f"❌ Error approving receipt: {str(e)}")
        if db:
            try:
                db.rollback()
                db.close()
            except:
                pass
        return {"status": "error", "message": str(e)}

# ==============================================
# API ENDPOINTS FOR SETTINGS
# ==============================================

@router.get("/api/settings/user-format")
async def get_user_format_settings():
    """Get user format settings."""
    try:
        db = SessionLocal()
        setting = db.query(SettingsDB).filter(SettingsDB.key == "user_format").first()
        db.close()

        if setting:
            return {"status": "success", "data": setting.value}
        else:
            # Default settings
            default = {
                "prefix": "user_",
                "start_number": 1000,
                "use_random_suffix": True,
                "random_suffix_length": 8,
                "sequential": True
            }
            return {"status": "success", "data": default}
    except Exception as e:
        logger.error(f"Error getting user format settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/user-format")
async def save_user_format_settings(request: Request):
    """Save user format settings."""
    try:
        data = await request.json()
        db = SessionLocal()

        setting = db.query(SettingsDB).filter(SettingsDB.key == "user_format").first()
        if setting:
            setting.value = data
            setting.updated_at = datetime.now()
        else:
            setting = SettingsDB(key="user_format", value=data)
            db.add(setting)

        db.commit()
        db.close()

        logger.info("User format settings updated")
        return {"status": "success", "message": "تنظیمات با موفقیت ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving user format settings: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# API ENDPOINTS FOR TEST ACCOUNT SETTINGS
# ==============================================

@router.get("/api/settings/test-account")
async def get_test_account_settings():
    """Get test account settings."""
    try:
        db = SessionLocal()
        setting = db.query(TestAccountSettingsDB).first()

        if not setting:
            setting = TestAccountSettingsDB(
                is_enabled=True,
                volume_mb=100,
                duration_days=1,
                max_per_week=2,
                limit_days=7
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)

        result = {
            "is_enabled": setting.is_enabled,
            "volume_mb": setting.volume_mb,
            "duration_days": setting.duration_days,
            "max_per_week": setting.max_per_week,
            "limit_days": setting.limit_days
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting test account settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/test-account")
async def save_test_account_settings(request: Request):
    """Save test account settings."""
    try:
        data = await request.json()
        db = SessionLocal()

        setting = db.query(TestAccountSettingsDB).first()
        if not setting:
            setting = TestAccountSettingsDB()
            db.add(setting)

        setting.is_enabled = data.get("is_enabled", True)
        setting.volume_mb = int(data.get("volume_mb", 100))
        setting.duration_days = int(data.get("duration_days", 1))
        setting.max_per_week = int(data.get("max_per_week", 2))
        setting.limit_days = int(data.get("limit_days", 7))
        setting.updated_at = datetime.now()

        db.commit()
        db.close()

        logger.info("Test account settings updated")
        return {"status": "success", "message": "تنظیمات با موفقیت ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving test account settings: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# API ENDPOINTS FOR TEST ACCOUNTS
# ==============================================

@router.get("/api/test-accounts/check/{user_id}")
async def check_test_account_eligibility(user_id: int):
    """Check if user can get test account."""
    try:
        db = SessionLocal()

        setting = db.query(TestAccountSettingsDB).first()
        if not setting:
            setting = TestAccountSettingsDB()
            db.add(setting)
            db.commit()
            db.refresh(setting)

        if not setting.is_enabled:
            db.close()
            return {"status": "success", "data": {"can_get": False, "reason": "disabled"}}

        # محاسبه شروع هفته (شنبه)
        today = datetime.now().date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_start_datetime = datetime.combine(week_start, datetime.min.time())

        # شمارش اکانت‌های تست این هفته
        count = db.query(TestAccountDB).filter(
            TestAccountDB.user_id == user_id,
            TestAccountDB.created_at >= week_start_datetime
        ).count()

        db.close()

        max_per_week = setting.max_per_week
        remaining = max(0, max_per_week - count)

        return {
            "status": "success",
            "data": {
                "can_get": remaining > 0,
                "remaining": remaining,
                "total": max_per_week,
                "week_start": week_start.isoformat(),
                "count_this_week": count
            }
        }
    except Exception as e:
        logger.error(f"Error checking test account eligibility: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/test-accounts/create")
async def create_test_account(request: Request):
    """Create a test account."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username")
        panel_id = data.get("panel_id")
        
        if not user_id or not panel_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        db = SessionLocal()
        
        # بررسی تنظیمات
        setting = db.query(TestAccountSettingsDB).first()
        if not setting:
            setting = TestAccountSettingsDB()
            db.add(setting)
            db.commit()
            db.refresh(setting)
        
        if not setting.is_enabled:
            db.close()
            return {"status": "error", "message": "اکانت تست غیرفعال است"}
        
        # بررسی محدودیت
        today = datetime.now().date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_start_datetime = datetime.combine(week_start, datetime.min.time())
        
        count = db.query(TestAccountDB).filter(
            TestAccountDB.user_id == user_id,
            TestAccountDB.created_at >= week_start_datetime
        ).count()
        
        if count >= setting.max_per_week:
            db.close()
            return {
                "status": "error", 
                "message": f"شما {setting.max_per_week} بار در این هفته اکانت تست گرفته‌اید. لطفاً هفته آینده مجدداً تلاش کنید."
            }
        
        # دریافت پنل
        panel = db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        # ====== ذخیره اطلاعات پنل قبل از بستن session ======
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        panel_name = panel.name
        panel_sub_url = panel.sub_url or ""
        panel_inbound_ids = panel.inbound_ids or []
        
        # ====== ذخیره تنظیمات قبل از بستن session ======
        test_volume_mb = setting.volume_mb
        test_duration_days = setting.duration_days
        test_max_per_week = setting.max_per_week
        
        # ====== ساخت نام کاربری ======
        # شمارش کل اکانت‌های تست این کاربر (نه فقط این هفته)
        total_test_count = db.query(TestAccountDB).filter(
            TestAccountDB.user_id == user_id
        ).count()
        
        # شمارنده جدید = تعداد کل + 1
        test_number = total_test_count + 1
        
        # پاکسازی username تلگرام (حذف کاراکترهای غیرمجاز)
        clean_telegram_username = username.replace("@", "").replace(" ", "_") if username else "user"
        
        # ساخت نام کاربری با تاریخ شمسی
        import jdatetime
        today_jalali = jdatetime.date.fromgregorian(date=datetime.now().date())
        jalali_str = f"{today_jalali.year:04d}{today_jalali.month:02d}{today_jalali.day:02d}"
        
        client_email = f"test_{jalali_str}_{clean_telegram_username}_{test_number}"
        
        # محاسبه حجم و زمان
        total_gb = test_volume_mb * 1048576  # تبدیل مگابایت به بایت
        expiry_time = int((datetime.now() + timedelta(days=test_duration_days)).timestamp() * 1000)
        
        # ساخت subId
        import uuid
        client_sub_id = str(uuid.uuid4())
        
        # دریافت inbound ID
        inbound_ids = []
        for inbound_id in panel_inbound_ids:
            try:
                inbound_ids.append(int(inbound_id))
            except:
                pass
        
        if not inbound_ids:
            db.close()
            return {"status": "error", "message": "هیچ Inboundی برای این پنل تعریف نشده است"}
        
        # آماده‌سازی داده برای پنل
        client_data = {
            "client": {
                "email": client_email,
                "totalGB": total_gb,
                "expiryTime": expiry_time,
                "tgId": user_id,
                "limitIp": 1,
                "enable": True,
                "subId": client_sub_id
            },
            "inboundIds": inbound_ids
        }
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }
        
        # ارسال به پنل
        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/add",
                headers=headers,
                json=client_data
            )
            
            if response.status_code != 200:
                db.close()
                return {"status": "error", "message": f"خطا در ساخت اکانت تست: {response.text}"}
            
            result = response.json()
            if not result.get("success"):
                db.close()
                return {"status": "error", "message": result.get("msg", "خطا در ساخت اکانت")}
        
        # ذخیره در دیتابیس
        test_account = TestAccountDB(
            user_id=user_id,
            username=username,
            panel_id=panel_id,
            panel_name=panel_name,
            client_email=client_email,
            client_sub_id=client_sub_id,
            volume_mb=test_volume_mb,
            duration_days=test_duration_days,
            expiry_time=expiry_time
        )
        db.add(test_account)
        db.commit()
        db.close()
        
        # ساخت لینک ساب
        sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else None
        
        return {
            "status": "success",
            "message": "اکانت تست با موفقیت ساخته شد",
            "data": {
                "client_email": client_email,
                "client_sub_id": client_sub_id,
                "sub_url": sub_url,
                "volume_mb": test_volume_mb,
                "duration_days": test_duration_days,
                "panel_name": panel_name,
                "expiry_time": expiry_time,
                "test_number": test_number
            }
        }
    except Exception as e:
        logger.error(f"Error creating test account: {str(e)}")
        return {"status": "error", "message": str(e)}





    # ==============================================
# CLEANUP EXPIRED TEST ACCOUNTS
# ==============================================

@router.post("/api/test-accounts/cleanup")
async def cleanup_expired_test_accounts():
    """Delete expired test accounts from all panels."""
    try:
        db = SessionLocal()
        
        setting = db.query(TestAccountSettingsDB).first()
        if not setting:
            db.close()
            return {"status": "error", "message": "تنظیمات اکانت تست یافت نشد"}
        
        now = datetime.now()
        now_timestamp = int(now.timestamp() * 1000)
        
        expired_accounts = db.query(TestAccountDB).filter(
            TestAccountDB.expiry_time > 0,
            TestAccountDB.expiry_time < now_timestamp
        ).all()
        
        if not expired_accounts:
            db.close()
            logger.info("No expired test accounts found")
            return {
                "status": "success",
                "message": "هیچ اکانت تست منقضی شده‌ای یافت نشد",
                "data": {"deleted_count": 0}
            }
        
        logger.info(f"Found {len(expired_accounts)} expired test accounts to delete")
        
        deleted_count = 0
        failed_count = 0
        results = []
        
        for account in expired_accounts:
            try:
                panel = db.query(PanelDB).filter(PanelDB.id == account.panel_id).first()
                
                if not panel:
                    # پنل وجود نداره - از دیتابیس حذف کن
                    db.delete(account)
                    deleted_count += 1
                    results.append({
                        "email": account.client_email,
                        "status": "deleted_from_db_only",
                        "reason": "panel_not_found"
                    })
                    continue
                
                panel_url = panel.url.rstrip("/")
                panel_api_token = panel.api_token
                
                delete_url = f"{panel_url}/panel/api/clients/del/{account.client_email}?keepTraffic=1"
                
                headers = {
                    "accept": "application/json",
                    "Authorization": f"Bearer {panel_api_token}"
                }
                
                async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                    response = await http_client.post(
                        delete_url,
                        headers=headers,
                        data=""
                    )
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        
                        if result_data.get("success"):
                            # حذف موفق
                            db.delete(account)
                            deleted_count += 1
                            results.append({
                                "email": account.client_email,
                                "status": "deleted",
                                "panel": panel.name
                            })
                            logger.info(f"✅ Deleted: {account.client_email}")
                        else:
                            # ✅ چک کن اگه "not found" بود، از دیتابیس حذف کن
                            msg = result_data.get("msg", "").lower()
                            if "not found" in msg or "client" in msg:
                                db.delete(account)
                                deleted_count += 1
                                results.append({
                                    "email": account.client_email,
                                    "status": "deleted_from_db_only",
                                    "reason": "not_found_in_panel"
                                })
                                logger.info(f"✅ Deleted from DB (not found in panel): {account.client_email}")
                            else:
                                failed_count += 1
                                results.append({
                                    "email": account.client_email,
                                    "status": "failed",
                                    "reason": result_data.get("msg", "unknown_error")
                                })
                                logger.warning(f"❌ Failed: {account.client_email}: {result_data.get('msg')}")
                    elif response.status_code == 404:
                        # ✅ 404 یعنی پیدا نشد - از دیتابیس حذف کن
                        db.delete(account)
                        deleted_count += 1
                        results.append({
                            "email": account.client_email,
                            "status": "deleted_from_db_only",
                            "reason": "not_found_in_panel"
                        })
                        logger.info(f"✅ Deleted from DB (404): {account.client_email}")
                    else:
                        failed_count += 1
                        results.append({
                            "email": account.client_email,
                            "status": "failed",
                            "reason": f"http_{response.status_code}"
                        })
                        logger.warning(f"❌ HTTP {response.status_code}: {account.client_email}")
                        
            except Exception as e:
                failed_count += 1
                results.append({
                    "email": account.client_email,
                    "status": "failed",
                    "reason": str(e)
                })
                logger.error(f"❌ Error: {account.client_email}: {str(e)}")
        
        db.commit()
        db.close()
        
        logger.info(f"Cleanup completed: {deleted_count} deleted, {failed_count} failed")
        
        return {
            "status": "success",
            "message": f"پاکسازی کامل شد: {deleted_count} حذف شد، {failed_count} خطا",
            "data": {
                "total_found": len(expired_accounts),
                "deleted_count": deleted_count,
                "failed_count": failed_count,
                "results": results
            }
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up expired test accounts: {str(e)}")
        if db:
            try:
                db.rollback()
                db.close()
            except:
                pass
        return {"status": "error", "message": str(e)}


@router.post("/api/payment/test")
async def test_payment_request(request: Request):
    """
    Test endpoint for creating Zarinpal payment request.
    """
    try:
        data = await request.json()
        amount = data.get("amount", 10000)
        
        logger.info(f"🧪 Test payment request received:")
        logger.info(f"   Amount: {amount}")
        
        # ارسال درخواست به زرین‌پال (sandbox)
        zarinpal_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        
        payment_data = {
            "merchant_id": "00000000-0000-0000-0000-000000000000",  # Sandbox
            "amount": amount,
            "callback_url": "https://bot.spacegate.ir/admin/api/payment/callback",
            "description": "تست پرداخت"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                zarinpal_url,
                json=payment_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            result = response.json()
            
            logger.info(f"Zarinpal response: {result}")
            
            if result.get("data") and result["data"].get("authority"):
                authority = result["data"]["authority"]
                payment_url = f"https://sandbox.zarinpal.com/pg/StartPay/{authority}"
                
                return {
                    "status": "success",
                    "message": "فاکتور با موفقیت ساخته شد",
                    "data": {
                        "authority": authority,
                        "payment_url": payment_url,
                        "amount": amount
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "خطا در ساخت فاکتور",
                    "data": result
                }
                
    except Exception as e:
        logger.error(f"Error in test payment: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# API ENDPOINTS FOR PAYMENT SETTINGS
# ==============================================

@router.get("/api/settings/payment")
async def get_payment_settings():
    """Get payment settings."""
    try:
        db = SessionLocal()
        setting = db.query(PaymentSettingsDB).first()

        if not setting:
            setting = PaymentSettingsDB(
                online_payment_enabled=False,
                receipt_payment_enabled=True,
                merchant_id="",
                sandbox_mode=True,
                card_numbers=[]
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)

        result = {
            "online_payment_enabled": setting.online_payment_enabled,
            "receipt_payment_enabled": setting.receipt_payment_enabled,
            "merchant_id": setting.merchant_id or "",
            "sandbox_mode": setting.sandbox_mode,
            "card_numbers": setting.card_numbers or []
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting payment settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/payment")
async def save_payment_settings(request: Request):
    """Save payment settings."""
    try:
        data = await request.json()
        db = SessionLocal()

        setting = db.query(PaymentSettingsDB).first()
        if not setting:
            setting = PaymentSettingsDB()
            db.add(setting)

        setting.online_payment_enabled = data.get("online_payment_enabled", False)
        setting.receipt_payment_enabled = data.get("receipt_payment_enabled", True)
        setting.merchant_id = data.get("merchant_id", "")
        setting.sandbox_mode = data.get("sandbox_mode", True)
        setting.card_numbers = data.get("card_numbers", []) 
        setting.updated_at = datetime.now()

        db.commit()
        db.close()

        logger.info("Payment settings updated")
        return {"status": "success", "message": "تنظیمات پرداخت با موفقیت ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving payment settings: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# API ENDPOINTS FOR PAYMENT
# ==============================================

@router.post("/api/payment/create")
async def create_payment(request: Request):
    """Create a payment request."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username", "")
        service_id = data.get("service_id")
        amount = data.get("amount")
        payment_type = data.get("payment_type", "new_purchase")
        is_renewal = data.get("is_renewal", False)
        renew_user_info = data.get("renewal_info")

        
        if not user_id or not amount:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        if payment_type != "settlement" and not service_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}

        db = SessionLocal()

        # دریافت تنظیمات پرداخت
        payment_setting = db.query(PaymentSettingsDB).first()
        if not payment_setting:
            db.close()
            return {"status": "error", "message": "تنظیمات پرداخت یافت نشد"}

        if not payment_setting.online_payment_enabled:
            db.close()
            return {"status": "error", "message": "پرداخت آنلاین غیرفعال است"}

        merchant_id = payment_setting.merchant_id
        if not merchant_id:
            db.close()
            return {"status": "error", "message": "مرچنت کد تنظیم نشده است"}

        # انتخاب سرور زرین‌پال
        if payment_setting.sandbox_mode:
            zarinpal_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        else:
            zarinpal_url = "https://api.zarinpal.com/pg/v4/payment/request.json"

        callback_url = "https://bot.spacegate.ir/admin/api/payment/callback"

        payment_data = {
            "merchant_id": merchant_id,
            "amount": amount,
            "callback_url": callback_url,
            "description": f"خرید سرویس {service_id} - کاربر {user_id}",
            "metadata": {
                "user_id": str(user_id),
                "service_id": str(service_id),
                "payment_type": payment_type
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                zarinpal_url,
                json=payment_data,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
            result = response.json()

            if result.get("data") and result["data"].get("authority"):
                authority = result["data"]["authority"]

                if payment_setting.sandbox_mode:
                    payment_url = f"https://sandbox.zarinpal.com/pg/StartPay/{authority}"
                else:
                    payment_url = f"https://payment.zarinpal.com/pg/StartPay/{authority}"

                # ====== ذخیره در دیتابیس ======
                new_payment = PaymentDB(
                    user_id=user_id,
                    username=username,
                    service_id=service_id,
                    amount=amount,
                    authority=authority,
                    status="pending",
                    payment_type=payment_type,
                    is_renewal=is_renewal,
                    renew_user_info=renew_user_info
                )
                db.add(new_payment)
                db.commit()
                db.refresh(new_payment)
                db.close()

                return {
                    "status": "success",
                    "message": "فاکتور ساخته شد",
                    "data": {
                        "payment_id": new_payment.id,
                        "authority": authority,
                        "payment_url": payment_url,
                        "amount": amount
                    }
                }
            else:
                db.close()
                return {"status": "error", "message": "خطا در ساخت فاکتور", "data": result}

    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/api/payment/callback")
async def payment_callback(request: Request):
    """Payment callback from Zarinpal."""
    authority = request.query_params.get("Authority") or request.query_params.get("authority")
    status = request.query_params.get("Status") or request.query_params.get("status")
    
    logger.info(f"🔔 Payment callback received! Authority: {authority}, Status: {status}")
    
    if status == "OK" and authority:
        try:
            db = SessionLocal()
            
            # پیدا کردن پرداخت
            payment = db.query(PaymentDB).filter(PaymentDB.authority == authority).first()
            if not payment:
                db.close()
                return templates.TemplateResponse("payment_result.html", {
                    "request": request,
                    "success": False,
                    "message": "پرداخت یافت نشد"
                })
            
            payment_setting = db.query(PaymentSettingsDB).first()
            if not payment_setting:
                db.close()
                return templates.TemplateResponse("payment_result.html", {
                    "request": request,
                    "success": False,
                    "message": "تنظیمات پرداخت یافت نشد"
                })
            
            # انتخاب سرور verify
            if payment_setting.sandbox_mode:
                verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
            else:
                verify_url = "https://api.zarinpal.com/pg/v4/payment/verify.json"
            
            verify_data = {
                "merchant_id": payment_setting.merchant_id,
                "amount": payment.amount,
                "authority": authority
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                verify_response = await client.post(
                    verify_url,
                    json=verify_data,
                    headers={"Content-Type": "application/json", "Accept": "application/json"}
                )
                verify_result = verify_response.json()
                logger.info(f"Verify result: {verify_result}")
                
                if verify_result.get("data") and verify_result["data"].get("code") == 100:
                    ref_id = str(verify_result["data"].get("ref_id"))
                    
                    if payment.payment_type == "settlement":
                        # Reset partner used_purchases
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as settle_client:
                                await settle_client.post(
                                    "http://localhost:8000/admin/api/sales/settle-payment",
                                    json={"partner_user_id": payment.user_id}
                                )
                            partner = db.query(SalesPartnerDB).filter(SalesPartnerDB.user_id == payment.user_id).first()
                            if partner:
                                await activate_all_partner_accounts(partner.id)
                            logger.info(f"✅ Settlement completed for partner {payment.user_id}")
                        except Exception as settle_error:
                            logger.error(f"Error settling payment: {str(settle_error)}")
                        
                        # Update payment status
                        payment.status = "paid"
                        payment.ref_id = ref_id
                        payment.paid_at = datetime.now()
                        db.commit()
                        db.close()
                        
                        return templates.TemplateResponse("payment_result.html", {
                            "request": request,
                            "success": True,
                            "message": "پرداخت تسویه با موفقیت انجام شد",
                            "data": {"ref_id": ref_id},
                            "ref_id": ref_id,
                            "is_renewal": False
                        })
                    
                    if payment.is_renewal:
                        # ====== RENEWAL PROCESS ======
                        result = await process_online_renewal(payment, db)
                    else:
                        # ====== NEW PURCHASE PROCESS ======
                        result = await process_online_purchase(payment, db)
                    
                    if result.get("status") == "success":
                        # بروزرسانی پرداخت
                        payment.status = "paid"
                        payment.ref_id = ref_id
                        payment.paid_at = datetime.now()
                        payment.client_email = result.get("data", {}).get("client_email")
                        payment.client_sub_id = result.get("data", {}).get("client_sub_id")
                        db.commit()
                        
                        # ارسال پیام به کاربر در تلگرام
                        await send_payment_success_message(payment.user_id, result.get("data", {}), payment.is_renewal)
                        
                        db.close()
                        
                        # نمایش صفحه رسید HTML
                        return templates.TemplateResponse("payment_result.html", {
                            "request": request,
                            "success": True,
                            "message": "پرداخت با موفقیت انجام شد",
                            "data": result.get("data", {}),
                            "ref_id": ref_id,
                            "is_renewal": payment.is_renewal
                        })
                    else:
                        db.close()
                        return templates.TemplateResponse("payment_result.html", {
                            "request": request,
                            "success": False,
                            "message": result.get("message", "خطا در ساخت سرویس")
                        })
                else:
                    payment.status = "failed"
                    db.commit()
                    db.close()
                    return templates.TemplateResponse("payment_result.html", {
                        "request": request,
                        "success": False,
                        "message": "خطا در تأیید پرداخت"
                    })
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return templates.TemplateResponse("payment_result.html", {
                "request": request,
                "success": False,
                "message": f"خطا: {str(e)}"
            })
    else:
        return templates.TemplateResponse("payment_result.html", {
            "request": request,
            "success": False,
            "message": "پرداخت ناموفق بود"
        })



# ==============================================
# PAYMENT PROCESSING HELPERS
# ==============================================

async def process_online_purchase(payment, db):
    """Create new user account after successful payment."""
    try:
        service = db.query(ServiceDB).filter(ServiceDB.id == payment.service_id).first()
        if not service:
            return {"status": "error", "message": "سرویس پیدا نشد"}
        
        panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
        if not panel:
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        # Save panel info before closing session
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        panel_sub_url = panel.sub_url or ""
        panel_name = panel.name
        
        # Generate username
        email = await generate_username(payment.user_id)
        
        # Calculate volume
        if service.volume and service.volume != "unlimited":
            totalGB = int(service.volume) * 1073741824
        else:
            totalGB = 0
        
        # Calculate expiry
        duration_months = service.duration or 1
        expiry_time = int((datetime.now() + timedelta(days=duration_months * 30)).timestamp() * 1000)
        
        limit_ip = 3 if totalGB == 0 else 0
        
        inbound_ids = []
        if service.inbound_id:
            try:
                inbound_ids = [int(service.inbound_id)]
            except:
                pass
        
        if not inbound_ids:
            return {"status": "error", "message": "هیچ Inboundی تعریف نشده"}
        
        import uuid
        client_sub_id = str(uuid.uuid4())
        
        client_data = {
            "client": {
                "email": email,
                "totalGB": totalGB,
                "expiryTime": expiry_time,
                "tgId": payment.user_id,
                "limitIp": limit_ip,
                "enable": True,
                "subId": client_sub_id
            },
            "inboundIds": inbound_ids
        }
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/add",
                headers=headers,
                json=client_data
            )
            
            if response.status_code != 200:
                return {"status": "error", "message": "خطا در ساخت کاربر"}
            
            result = response.json()
            if not result.get("success"):
                return {"status": "error", "message": result.get("msg", "خطا در ساخت کاربر")}
        
        sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else None
        
        return {
            "status": "success",
            "data": {
                "client_email": email,
                "client_sub_id": client_sub_id,
                "sub_url": sub_url,
                "panel_name": panel_name,
                "volume": service.volume or "نامحدود",
                "duration": duration_months,
                "expiry_time": expiry_time
            }
        }
    except Exception as e:
        logger.error(f"Error processing online purchase: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_online_renewal(payment, db):
    """Renew user account after successful payment."""
    try:
        renew_user_info = payment.renew_user_info
        if not renew_user_info:
            return {"status": "error", "message": "اطلاعات تمدید یافت نشد"}
        
        service = db.query(ServiceDB).filter(ServiceDB.id == payment.service_id).first()
        if not service:
            return {"status": "error", "message": "سرویس پیدا نشد"}
        
        panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
        if not panel:
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        username = renew_user_info.get('email')
        client_data = renew_user_info.get('client', {})
        
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        panel_sub_url = panel.sub_url or ""
        panel_name = panel.name
        
        # Calculate time
        current_expiry_time = client_data.get('expiryTime', 0)
        remaining_days = 0
        if current_expiry_time > 0:
            current_expiry_date = datetime.fromtimestamp(current_expiry_time / 1000)
            remaining_days = max(0, (current_expiry_date - datetime.now()).days)
        
        duration_months = service.duration or 1
        new_days = duration_months * 30
        total_days = remaining_days + new_days
        new_expiry_time = int((datetime.now() + timedelta(days=total_days)).timestamp() * 1000)
        
        # Calculate volume
        current_total_bytes = client_data.get('totalGB', 0)
        current_used_bytes = client_data.get('usedGB', 0)
        if current_used_bytes == 0:
            current_used_bytes = client_data.get('usedTraffic', 0)
        
        if current_total_bytes > 0:
            remaining_bytes = max(0, current_total_bytes - current_used_bytes)
            if service.volume and service.volume != "unlimited":
                new_volume_bytes = int(service.volume) * 1073741824
            else:
                new_volume_bytes = 0
            new_total_bytes = remaining_bytes + new_volume_bytes
        else:
            new_total_bytes = 0
        
        update_data = {
            "email": username,
            "totalGB": new_total_bytes,
            "expiryTime": new_expiry_time,
            "tgId": client_data.get('tgId', payment.user_id),
            "limitIp": client_data.get('limitIp', 0),
            "enable": True,
            "subId": client_data.get('subId', '')
        }
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/update/{username}",
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                return {"status": "error", "message": "خطا در تمدید سرویس"}
            
            result = response.json()
            if not result.get("success"):
                return {"status": "error", "message": result.get("msg", "خطا در تمدید")}
        
        client_sub_id = client_data.get('subId', '')
        sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else None
        
        return {
            "status": "success",
            "data": {
                "client_email": username,
                "client_sub_id": client_sub_id,
                "sub_url": sub_url,
                "panel_name": panel_name,
                "volume": f"{new_total_bytes/1073741824:.1f} GB" if new_total_bytes > 0 else "نامحدود",
                "duration": total_days,
                "expiry_time": new_expiry_time
            }
        }
    except Exception as e:
        logger.error(f"Error processing online renewal: {str(e)}")
        return {"status": "error", "message": str(e)}


async def send_payment_success_message(user_id: int, data: dict, is_renewal: bool):
    """Send success message to user via Telegram."""
    try:
        if is_renewal:
            message = (
                f"✅ **تمدید سرویس با موفقیت انجام شد!**\n\n"
                f"📧 **یوزرنیم:** `{data.get('client_email')}`\n"
                f"🖥️ **پنل:** {data.get('panel_name')}\n"
                f"📊 **حجم:** {data.get('volume')}\n"
                f"⏰ **مدت:** {data.get('duration')} روز\n\n"
                f"🔗 **لینک سابسکریپشن:**\n{data.get('sub_url')}\n\n"
                f"💡 برای مشاهده اطلاعات از بخش 'وضعیت من' استفاده کنید."
            )
        else:
            message = (
                f"✅ **پرداخت شما تأیید شد!**\n\n"
                f"📧 **یوزرنیم:** `{data.get('client_email')}`\n"
                f"🖥️ **پنل:** {data.get('panel_name')}\n"
                f"📦 **حجم:** {data.get('volume')} GB\n"
                f"⏰ **مدت اعتبار:** {data.get('duration')} روز\n\n"
                f"🔗 **لینک سابسکریپشن:**\n{data.get('sub_url')}\n\n"
                f"📱 **نحوه استفاده:**\n"
                f"لینک سابسکریپشن را در اپلیکیشن خود وارد کنید.\n\n"
                f"⚠️ **لطفاً یوزرنیم خود را ذخیره کنید.**"
            )
        
        await send_message_to_user(user_id, message)
    except Exception as e:
        logger.error(f"Error sending payment success message: {str(e)}")

# ==============================================
# API ENDPOINTS FOR REFERRAL SETTINGS
# ==============================================

@router.get("/api/settings/referral")
async def get_referral_settings():
    """Get referral settings."""
    try:
        db = SessionLocal()
        setting = db.query(ReferralSettingsDB).first()
        
        if not setting:
            setting = ReferralSettingsDB(
                is_enabled=True,
                first_purchase_discount=10,
                recurring_discount=5,
                min_redeem_percent=100
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        
        result = {
            "is_enabled": setting.is_enabled,
            "first_purchase_discount": setting.first_purchase_discount,
            "recurring_discount": setting.recurring_discount,
            "min_redeem_percent": setting.min_redeem_percent
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting referral settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/referral")
async def save_referral_settings(request: Request):
    """Save referral settings."""
    try:
        data = await request.json()
        db = SessionLocal()
        
        setting = db.query(ReferralSettingsDB).first()
        if not setting:
            setting = ReferralSettingsDB()
            db.add(setting)
        
        setting.is_enabled = data.get("is_enabled", True)
        setting.first_purchase_discount = int(data.get("first_purchase_discount", 10))
        setting.recurring_discount = int(data.get("recurring_discount", 5))
        setting.min_redeem_percent = int(data.get("min_redeem_percent", 100))

        setting.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        logger.info("Referral settings updated")
        return {"status": "success", "message": "تنظیمات رفرال با موفقیت ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving referral settings: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# API ENDPOINTS FOR REFERRALS
# ==============================================

@router.get("/api/referrals/stats/{user_id}")
async def get_referral_stats(user_id: int):
    """Get referral statistics for a user."""
    try:
        db = SessionLocal()
        
        # دریافت تنظیمات
        setting = db.query(ReferralSettingsDB).first()
        if not setting:
            setting = ReferralSettingsDB()
            db.add(setting)
            db.commit()
            db.refresh(setting)
        
        # لینک رفرال
        referral_link = f"https://t.me/SpaceGateBot?start=ref_{user_id}"
        
        # تعداد کل معرفی‌ها
        total_referrals = db.query(ReferralDB).filter(
            ReferralDB.referrer_id == user_id,
            ReferralDB.is_used == True
        ).count()
        
        # دریافت لیست زیرمجموعه‌ها
        referrals = db.query(ReferralDB).filter(
            ReferralDB.referrer_id == user_id,
            ReferralDB.is_used == True
        ).all()
        
        # بررسی فعال بودن هر کاربر
        active_users = []
        now_timestamp = int(datetime.now().timestamp() * 1000)
        
        for ref in referrals:
            # چک کردن اینکه آیا کاربر سرویس فعال داره
            # با جستجو در پنل‌ها
            is_active = False
            try:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker as sm
                
                engine2 = create_engine(settings.DATABASE_URL)
                SessionLocal2 = sm(bind=engine2)
                db2 = SessionLocal2()
                
                panels = db2.query(PanelDB).all()
                db2.close()
                
                for panel in panels:
                    panel_url = panel.url.rstrip("/")
                    api_token = panel.api_token
                    
                    headers = {
                        "accept": "application/json",
                        "Authorization": f"Bearer {api_token}",
                        "User-Agent": "curl/7.81.0"
                    }
                    
                    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                        resp = await client.get(
                            f"{panel_url}/panel/api/clients/list",
                            headers=headers
                        )
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            clients = data.get("obj", []) if isinstance(data, dict) else data
                            
                            for client_obj in clients:
                                if client_obj.get("tgId") == ref.referred_id:
                                    expiry_time = client_obj.get("expiryTime", 0)
                                    if expiry_time == 0:
                                        # نامحدود
                                        is_active = True
                                    elif expiry_time > now_timestamp:
                                        is_active = True
                                    
                                    if is_active:
                                        break
                        
                        if is_active:
                            break
                
                if is_active:
                    active_users.append({
                        "user_id": ref.referred_id,
                        "joined_at": ref.created_at.isoformat() if ref.created_at else None
                    })
            except Exception as e:
                logger.error(f"Error checking active status: {str(e)}")
        
        # دریافت اعتبار تخفیف
        discount = db.query(ReferralDiscountDB).filter(
            ReferralDiscountDB.user_id == user_id
        ).first()
        
        if discount:
            total_percent = discount.total_percent
            used_percent = discount.used_percent
            remaining_percent = discount.remaining_percent
        else:
            total_percent = 0
            used_percent = 0
            remaining_percent = 0
        
        db.close()
        
        return {
            "status": "success",
            "data": {
                "referral_link": referral_link,
                "total_referrals": total_referrals,
                "active_count": len(active_users),
                "active_users": active_users,
                "discount": {
                    "total_percent": total_percent,
                    "used_percent": used_percent,
                    "remaining_percent": remaining_percent
                },
                "min_redeem_percent": setting.min_redeem_percent
            }
        }
    except Exception as e:
        logger.error(f"Error getting referral stats: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/referrals/register")
async def register_referral(request: Request):
    """Register a new referral when user uses referral code."""
    try:
        data = await request.json()
        referrer_id = data.get("referrer_id")
        referred_id = data.get("referred_id")
        
        if not referrer_id or not referred_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        if referrer_id == referred_id:
            return {"status": "error", "message": "نمی‌توانید از کد خودتان استفاده کنید"}
        
        db = SessionLocal()
        
        # بررسی تنظیمات
        setting = db.query(ReferralSettingsDB).first()
        if not setting or not setting.is_enabled:
            db.close()
            return {"status": "error", "message": "سیستم رفرال غیرفعال است"}
        
        existing = db.query(ReferralDB).filter(
            ReferralDB.referred_id == referred_id
        ).first() 

        if existing:
            db.close()
            return {"status": "error", "message": "شما قبلاً از کد رفرال استفاده کرده‌اید"}
        
        # ثبت رفرال جدید
        new_referral = ReferralDB(
            referrer_id=referrer_id,
            referred_id=referred_id,
            discount_percent=setting.first_purchase_discount,
            is_used=False
        )

        db.add(new_referral)
        db.commit()
        db.refresh(new_referral)
        db.close()
        
        return {
            "status": "success",
            "message": "کد رفرال با موفقیت ثبت شد",
            "data": {
                "referral_id": new_referral.id,
                "discount_percent": referral.discount_percent 
            }
        }
    except Exception as e:
        logger.error(f"Error registering referral: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/referrals/apply")
async def apply_referral_discount(request: Request):
    """Apply referral discount when user makes a purchase."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        db = SessionLocal()
        
        # پیدا کردن رفرال استفاده نشده
        referral = db.query(ReferralDB).filter(
            ReferralDB.referred_id == user_id,
            ReferralDB.is_used == False
        ).first()
        
        if not referral:
            db.close()
            return {"status": "success", "data": {"discount_percent": 0}}
        
        discount_percent = referral.discount_percent
        
        # علامت‌گذاری به عنوان استفاده شده
        referral.is_used = True
        referral.used_at = datetime.now()
        
        # اضافه کردن اعتبار به معرف
        discount = db.query(ReferralDiscountDB).filter(
            ReferralDiscountDB.user_id == referral.referrer_id
        ).first()
        
        if not discount:
            discount = ReferralDiscountDB(
                user_id=referral.referrer_id,
                total_percent=0,
                used_percent=0,
                remaining_percent=0
            )
            db.add(discount)
        
        discount.total_percent += discount_percent
        discount.remaining_percent += discount_percent
        discount.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        return {
            "status": "success",
            "data": {
                "discount_percent": discount_percent
            }
        }
    except Exception as e:
        logger.error(f"Error applying referral discount: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/referrals/apply-recurring")
async def apply_recurring_discount(request: Request):
    """Apply recurring discount when referred user makes purchases after first."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        db = SessionLocal()
        
        # پیدا کردن زیرمجموعه بودن کاربر
        referral = db.query(ReferralDB).filter(
            ReferralDB.referred_id == user_id
        ).first()
        
        if not referral:
            db.close()
            return {"status": "success", "data": {"applied": False}}
        
        # دریافت تنظیمات
        setting = db.query(ReferralSettingsDB).first()
        if not setting or not setting.is_enabled:
            db.close()
            return {"status": "success", "data": {"applied": False}}
        
        recurring_percent = setting.recurring_discount
        
        # اضافه کردن اعتبار به معرف
        discount = db.query(ReferralDiscountDB).filter(
            ReferralDiscountDB.user_id == referral.referrer_id
        ).first()
        
        if not discount:
            discount = ReferralDiscountDB(
                user_id=referral.referrer_id,
                total_percent=0,
                used_percent=0,
                remaining_percent=0
            )
            db.add(discount)
        
        discount.total_percent += recurring_percent
        discount.remaining_percent += recurring_percent
        discount.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        return {
            "status": "success",
            "data": {
                "applied": True,
                "percent": recurring_percent,
                "referrer_id": referral.referrer_id
            }
        }
    except Exception as e:
        logger.error(f"Error applying recurring discount: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/referrals/redeem")
async def redeem_referral_discount(request: Request):
    """Redeem referral discount for renewal."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        db = SessionLocal()
        
        discount = db.query(ReferralDiscountDB).filter(
            ReferralDiscountDB.user_id == user_id
        ).first()
        
        if not discount:
            db.close()
            return {"status": "error", "message": "اعتبار تخفیف یافت نشد"}
        
        setting = db.query(ReferralSettingsDB).first()
        min_percent = setting.min_redeem_percent if setting else 100
        
        if discount.remaining_percent < min_percent:
            db.close()
            return {"status": "error", "message": f"اعتبار شما کمتر از {min_percent}% است"}
        
        # استفاده از min_percent درصد
        discount.used_percent += min_percent
        discount.remaining_percent -= min_percent
        discount.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        return {
            "status": "success",
            "message": f"{min_percent}% تخفیف اعمال شد",
            "data": {
                "redeemed_percent": min_percent,
                "remaining_percent": discount.remaining_percent
            }
        }
    except Exception as e:
        logger.error(f"Error redeeming referral discount: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/referrals/check")
async def check_referral_discount(request: Request):
    """Check if user has unused referral discount without applying it."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return {"status": "error", "message": "اطلاعات ناقص است"}
        
        db = SessionLocal()
        
        # پیدا کردن رفرال استفاده نشده
        referral = db.query(ReferralDB).filter(
            ReferralDB.referred_id == user_id,
            ReferralDB.is_used == False
        ).first()
        
        if not referral:
            db.close()
            return {"status": "success", "data": {"discount_percent": 0}}
        
        discount_percent = referral.discount_percent
        db.close()
        
        return {
            "status": "success",
            "data": {
                "discount_percent": discount_percent,
                "referral_id": referral.id
            }
        }
    except Exception as e:
        logger.error(f"Error checking referral discount: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/settings/channel")
async def get_channel_settings():
    """Get channel settings."""
    try:
        db = SessionLocal()
        setting = db.query(ChannelSettingsDB).first()
        
        if not setting:
            setting = ChannelSettingsDB(
                channel_username="",
                channel_chat_id="",
                channel_url="",
                is_enabled=False
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        
        result = {
            "channel_username": setting.channel_username or "",
            "channel_chat_id": setting.channel_chat_id or "",
            "channel_url": setting.channel_url or "",
            "is_enabled": setting.is_enabled
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting channel settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/channel")
async def save_channel_settings(request: Request):
    """Save channel settings."""
    try:
        data = await request.json()
        db = SessionLocal()
        
        setting = db.query(ChannelSettingsDB).first()
        if not setting:
            setting = ChannelSettingsDB()
            db.add(setting)
        
        setting.channel_username = data.get("channel_username", "")
        setting.channel_chat_id = data.get("channel_chat_id", "")  
        setting.channel_url = data.get("channel_url", "")
        setting.is_enabled = data.get("is_enabled", True)
        setting.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        return {"status": "success", "message": "تنظیمات کانال ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving channel settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/check-membership/{user_id}")
async def check_membership(user_id: int):
    """Check if user is member of the channel."""
    try:
        db = SessionLocal()
        setting = db.query(ChannelSettingsDB).first()

        if not setting or not setting.is_enabled:
            db.close()
            return {"status": "success", "data": {"is_member": True, "channel_settings": None}}

        db.close()

        from api.routes.webhook import application

        try:
            # ✅ استفاده از chat_id عددی
            if setting.channel_chat_id:
                chat_id = setting.channel_chat_id
            elif setting.channel_username:
                chat_id = f"@{setting.channel_username.replace('@', '')}"
            else:
                return {"status": "success", "data": {"is_member": True, "channel_settings": None}}

            chat_member = await application.bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )

            is_member = chat_member.status in ['member', 'administrator', 'creator']

            return {
                "status": "success",
                "data": {
                    "is_member": is_member,
                    "channel_settings": {
                        "channel_username": setting.channel_username,
                        "channel_url": setting.channel_url
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error checking membership: {str(e)}")
            return {"status": "success", "data": {"is_member": True, "channel_settings": None}}
    except Exception as e:
        logger.error(f"Error checking membership: {str(e)}")
        return {"status": "success", "data": {"is_member": True, "channel_settings": None}}


# ==============================================
# API ENDPOINTS FOR BROADCAST
# ==============================================

@router.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request):
    """Broadcast message page."""
    logger.info("Broadcast page accessed")
    context = {
        "request": request,
        "active": "broadcast"
    }
    return templates.TemplateResponse("broadcast.html", context)


@router.get("/api/users/count")
async def get_users_count():
    """Get total users count."""
    try:
        db = SessionLocal()
        count = db.query(UserDB).count()
        db.close()
        return {"status": "success", "data": {"count": count}}
    except Exception as e:
        logger.error(f"Error getting users count: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/broadcast/send")
async def send_broadcast(request: Request):
    """Send broadcast message to all users."""
    try:
        data = await request.json()
        message_text = data.get("text", "")
        photo_path = data.get("photo_path", None)

        if not message_text and not photo_path:
            return {"status": "error", "message": "متن پیام یا عکس الزامی است"}

        db = SessionLocal()
        users = db.query(UserDB).all()
        db.close()

        if not users:
            return {"status": "error", "message": "هیچ کاربری یافت نشد"}

        from api.routes.webhook import application

        success_count = 0
        failed_count = 0
        results = []

        # ارسال به همه کاربران
        for user in users:
            try:
                if photo_path:
                    # ارسال عکس با کپشن
                    with open(photo_path, 'rb') as photo_file:
                        await application.bot.send_photo(
                            chat_id=user.user_id,
                            photo=photo_file,
                            caption=message_text if message_text else None,
                            parse_mode="Markdown" if message_text else None
                        )
                else:
                    # ارسال متن
                    await application.bot.send_message(
                        chat_id=user.user_id,
                        text=message_text,
                        parse_mode="Markdown"
                    )

                success_count += 1
                results.append({"user_id": user.user_id, "status": "success"})

                # ⚠️ محدودیت تلگرام - 30 پیام در ثانیه
                await asyncio.sleep(0.05)  # 50ms delay

            except Exception as e:
                failed_count += 1
                results.append({"user_id": user.user_id, "status": "failed", "error": str(e)})
                logger.error(f"Failed to send to {user.user_id}: {str(e)}")

        return {
            "status": "success",
            "message": f"ارسال کامل شد: {success_count} موفق، {failed_count} خطا",
            "data": {
                "total": len(users),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }
        }

    except Exception as e:
        logger.error(f"Error sending broadcast: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/users/register")
async def register_user(request: Request):
    """Register a user in database."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        
        if not user_id:
            return {"status": "error", "message": "user_id الزامی است"}
        
        db = SessionLocal()
        
        existing = db.query(UserDB).filter(UserDB.user_id == user_id).first()
        
        if existing:
            # بروزرسانی
            existing.username = username
            existing.first_name = first_name
            existing.last_name = last_name
            existing.last_seen = datetime.now()
        else:
            # ثبت جدید
            new_user = UserDB(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(new_user)
        
        db.commit()
        db.close()
        
        return {"status": "success", "message": "کاربر ثبت شد"}
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return {"status": "error", "message": str(e)}




@router.post("/api/upload-photo")
async def upload_photo(request: Request):
    """Upload photo for broadcast."""
    try:
        from fastapi import UploadFile, File
        import shutil
        
        form = await request.form()
        photo = form.get("photo")
        
        if not photo:
            return {"status": "error", "message": "عکس یافت نشد"}
        
        import os
        os.makedirs("broadcast_photos", exist_ok=True)
        
        filename = f"broadcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = f"broadcast_photos/{filename}"
        
        with open(file_path, "wb") as f:
            content = await photo.read()
            f.write(content)
        
        return {
            "status": "success",
            "data": {"path": file_path}
        }
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# DASHBOARD API
# ==============================================

@router.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get all dashboard statistics."""
    try:
        db = SessionLocal()
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Users
        total_users = db.query(UserDB).count()
        new_users_today = db.query(UserDB).filter(
            UserDB.created_at >= today_start,
            UserDB.created_at <= today_end
        ).count()

        # Payments (online)
        paid_payments = db.query(PaymentDB).filter(
            PaymentDB.status == "paid"
        ).all()

        online_payments_today = db.query(PaymentDB).filter(
            PaymentDB.status == "paid",
            PaymentDB.paid_at >= today_start,
            PaymentDB.paid_at <= today_end
        ).count()

        total_revenue_today = sum(p.amount for p in db.query(PaymentDB).filter(
            PaymentDB.status == "paid",
            PaymentDB.paid_at >= today_start,
            PaymentDB.paid_at <= today_end
        ).all())

        # Receipts
        pending_receipts = db.query(ReceiptDB).filter(
            ReceiptDB.status == "pending"
        ).count()

        receipts_today = db.query(ReceiptDB).filter(
            ReceiptDB.created_at >= today_start,
            ReceiptDB.created_at <= today_end
        ).count()
        

        # Test accounts
        test_accounts_today = db.query(TestAccountDB).filter(
            TestAccountDB.created_at >= today_start,
            TestAccountDB.created_at <= today_end
        ).count()

        # Referrals
        new_referrals_today = db.query(ReferralDB).filter(
            ReferralDB.created_at >= today_start,
            ReferralDB.created_at <= today_end
        ).count()

        total_referrals = db.query(ReferralDB).count()
        active_referrals = db.query(ReferralDB).filter(
            ReferralDB.is_used == True
        ).count()

        # Panels
        panels = db.query(PanelDB).all()
        panels_status = []
        for panel in panels:
            panels_status.append({
                "id": panel.id,
                "name": panel.name,
                "status": panel.status,
                "users_count": panel.users_count,
                "is_full": panel.is_full
            })
        
        # Sales partners
        pending_sales_requests = db.query(SalesRequestDB).filter(
            SalesRequestDB.status == "pending"
        ).count()

        total_partners = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.is_active == True
        ).count()

        # Recent activities
        recent_receipts = db.query(ReceiptDB).order_by(ReceiptDB.created_at.desc()).limit(5).all()
        recent_payments = db.query(PaymentDB).filter(PaymentDB.status == "paid").order_by(PaymentDB.paid_at.desc()).limit(5).all()

                # ====== Recent Activities (Complete) ======
        activities = []
        
        # 1. New users (last 3)
        new_users = db.query(UserDB).order_by(UserDB.created_at.desc()).limit(3).all()
        for u in new_users:
            display_name = u.first_name or u.username or str(u.user_id)
            activities.append({
                "type": "user",
                "icon": "👤",
                "title": f"کاربر جدید: {display_name}",
                "time": u.created_at.isoformat() if u.created_at else None
            })
        
        # 2. Online payments paid (last 3)
        paid_payments = db.query(PaymentDB).filter(
            PaymentDB.status == "paid"
        ).order_by(PaymentDB.paid_at.desc()).limit(3).all()
        for p in paid_payments:
            activities.append({
                "type": "payment",
                "icon": "💳",
                "title": f"پرداخت آنلاین موفق: {p.amount:,} تومان",
                "time": p.paid_at.isoformat() if p.paid_at else None
            })
        
        # 3. New receipts (last 3)
        recent_receipts = db.query(ReceiptDB).order_by(
            ReceiptDB.created_at.desc()
        ).limit(3).all()
        for r in recent_receipts:
            display_name = r.username or str(r.user_id)
            status_text = {
                "pending": "در انتظار",
                "approved": "تایید شده",
                "rejected": "رد شده"
            }.get(r.status, r.status)
            activities.append({
                "type": "receipt",
                "icon": "📋",
                "title": f"رسید {status_text}: {display_name}",
                "time": r.created_at.isoformat() if r.created_at else None
            })
        
        # 4. Test accounts (last 2)
        recent_tests = db.query(TestAccountDB).order_by(
            TestAccountDB.created_at.desc()
        ).limit(2).all()
        for t in recent_tests:
            activities.append({
                "type": "test",
                "icon": "🎁",
                "title": f"اکانت تست ساخته شد: {t.client_email}",
                "time": t.created_at.isoformat() if t.created_at else None
            })
        
        # 5. New referrals (last 2)
        recent_refs = db.query(ReferralDB).order_by(
            ReferralDB.created_at.desc()
        ).limit(2).all()
        for ref in recent_refs:
            activities.append({
                "type": "referral",
                "icon": "🔗",
                "title": f"رفرال جدید: کاربر {ref.referred_id}",
                "time": ref.created_at.isoformat() if ref.created_at else None
            })
        
        # Sort by time (newest first) and limit to 10
        activities.sort(key=lambda x: x.get("time") or "", reverse=True)
        activities = activities[:10]

        # Sort activities by time
        activities.sort(key=lambda x: x.get("time") or "", reverse=True)
        activities = activities[:10]

        # Sales chart (last 7 days)
        sales_chart = {"labels": [], "data": []}
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            day_sales = sum(p.amount for p in db.query(PaymentDB).filter(
                PaymentDB.status == "paid",
                PaymentDB.paid_at >= day_start,
                PaymentDB.paid_at <= day_end
            ).all())

            sales_chart["labels"].append(day.strftime("%m/%d"))
            sales_chart["data"].append(day_sales)

        db.close()

        return {
            "status": "success",
            "data": {
                "total_users": total_users,
                "new_users_today": new_users_today,
                "pending_receipts": pending_receipts,
                "receipts_today": receipts_today,
                "online_payments_today": online_payments_today,
                "test_accounts_today": test_accounts_today,
                "new_referrals_today": new_referrals_today,
                "total_referrals": total_referrals,
                "active_referrals": active_referrals,
                "total_revenue_today": total_revenue_today,
                "panels": panels_status,
                "activities": activities,
                "sales_chart": sales_chart,
                "pending_sales_requests": pending_sales_requests,
                "total_partners": total_partners
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# REPORTS API
# ==============================================

@router.get("/api/reports/stats")
async def get_report_stats(date_from: str = None, date_to: str = None):
    """Get detailed report statistics."""
    try:
        db = SessionLocal()

        # Parse dates
        from_date = datetime.strptime(date_from, "%Y-%m-%d") if date_from else datetime.now() - timedelta(days=30)
        to_date = datetime.strptime(date_to, "%Y-%m-%d") if date_to else datetime.now()
        from_start = datetime.combine(from_date.date(), datetime.min.time())
        to_end = datetime.combine(to_date.date(), datetime.max.time())

        # ===== Sales =====
        paid_payments = db.query(PaymentDB).filter(
            PaymentDB.status == "paid",
            PaymentDB.paid_at >= from_start,
            PaymentDB.paid_at <= to_end
        ).all()

        total_revenue = sum(p.amount for p in paid_payments)
        total_transactions = len(paid_payments)
        avg_transaction = total_revenue // total_transactions if total_transactions > 0 else 0

        # ===== Revenue from receipts (card to card) =====
        approved_receipts = db.query(ReceiptDB).filter(
            ReceiptDB.status == "approved",
            ReceiptDB.processed_at >= from_start,
            ReceiptDB.processed_at <= to_end
        ).all()

        receipt_revenue = sum(
            (r.service_details.get("price") or 0) for r in approved_receipts if r.service_details
        )

        # Total revenue = online + receipts
        grand_total = total_revenue + receipt_revenue

        # ===== Growth rate =====
        # Compare with previous period
        period_days = (to_end - from_start).days
        prev_start = from_start - timedelta(days=period_days)
        prev_end = from_start

        prev_payments = db.query(PaymentDB).filter(
            PaymentDB.status == "paid",
            PaymentDB.paid_at >= prev_start,
            PaymentDB.paid_at <= prev_end
        ).all()

        prev_total = sum(p.amount for p in prev_payments)

        if prev_total > 0:
            growth_rate = ((total_revenue - prev_total) / prev_total) * 100
        else:
            growth_rate = 0

        # ===== Weekly sales chart =====
        weekly_sales = {"labels": [], "data": []}
        for i in range(3, -1, -1):
            week_start = from_start + timedelta(weeks=i)
            week_end = week_start + timedelta(days=7)

            week_payments = db.query(PaymentDB).filter(
                PaymentDB.status == "paid",
                PaymentDB.paid_at >= week_start,
                PaymentDB.paid_at <= week_end
            ).all()

            week_total = sum(p.amount for p in week_payments)
            weekly_sales["labels"].append(f"هفته {4-i}")
            weekly_sales["data"].append(week_total // 1000)  # به هزار تومان

        # ===== Service distribution =====
        service_distribution = {"labels": [], "data": []}
        services_sold = {}

        for p in paid_payments:
            service = db.query(ServiceDB).filter(ServiceDB.id == p.service_id).first()
            if service:
                key = service.name
                services_sold[key] = services_sold.get(key, 0) + 1

        for r in approved_receipts:
            key = r.service_name
            services_sold[key] = services_sold.get(key, 0) + 1

        # Sort and get top 6
        top_services = sorted(services_sold.items(), key=lambda x: x[1], reverse=True)[:6]
        service_distribution["labels"] = [s[0] for s in top_services]
        service_distribution["data"] = [s[1] for s in top_services]

        # ===== Payment methods =====
        online_count = len(paid_payments)
        receipt_count = len(approved_receipts)
        total_count = online_count + receipt_count

        payment_methods = {
            "online": online_count,
            "receipt": receipt_count,
            "online_percent": round((online_count / total_count * 100), 1) if total_count > 0 else 0,
            "receipt_percent": round((receipt_count / total_count * 100), 1) if total_count > 0 else 0
        }

        # ===== User stats =====
        new_users = db.query(UserDB).filter(
            UserDB.created_at >= from_start,
            UserDB.created_at <= to_end
        ).count()

        total_users = db.query(UserDB).count()

        # ===== Referral stats =====
        new_referrals = db.query(ReferralDB).filter(
            ReferralDB.created_at >= from_start,
            ReferralDB.created_at <= to_end
        ).count()

        total_referrals = db.query(ReferralDB).count()

        # ===== Test accounts =====
        new_test_accounts = db.query(TestAccountDB).filter(
            TestAccountDB.created_at >= from_start,
            TestAccountDB.created_at <= to_end
        ).count()

        db.close()

        return {
            "status": "success",
            "data": {
                "total_revenue": grand_total,
                "online_revenue": total_revenue,
                "receipt_revenue": receipt_revenue,
                "total_transactions": total_count,
                "avg_transaction": avg_transaction,
                "growth_rate": round(growth_rate, 1),
                "weekly_sales": weekly_sales,
                "service_distribution": service_distribution,
                "payment_methods": payment_methods,
                "new_users": new_users,
                "total_users": total_users,
                "new_referrals": new_referrals,
                "total_referrals": total_referrals,
                "new_test_accounts": new_test_accounts
            }
        }
    except Exception as e:
        logger.error(f"Error getting report stats: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# SALES PARTNER API
# ==============================================

@router.post("/api/sales/request")
async def create_sales_request(request: Request):
    """Create a sales partner request."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username")
        first_name = data.get("first_name")
        
        if not user_id:
            return {"status": "error", "message": "user_id الزامی است"}
        
        db = SessionLocal()
        
        # Check if already a partner
        existing_partner = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.user_id == user_id
        ).first()
        
        if existing_partner:
            db.close()
            return {"status": "error", "message": "شما قبلاً همکار هستید"}
        
        # Check if pending request exists
        existing_request = db.query(SalesRequestDB).filter(
            SalesRequestDB.user_id == user_id,
            SalesRequestDB.status == "pending"
        ).first()
        
        if existing_request:
            db.close()
            return {"status": "error", "message": "درخواست شما در حال بررسی است"}
        
        new_request = SalesRequestDB(
            user_id=user_id,
            username=username,
            first_name=first_name,
            status="pending"
        )
        db.add(new_request)
        db.commit()
        db.close()
        
        return {"status": "success", "message": "درخواست با موفقیت ثبت شد"}
    except Exception as e:
        logger.error(f"Error creating sales request: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sales/check/{user_id}")
async def check_sales_partner(user_id: int):
    """Check if user is a sales partner."""
    try:
        db = SessionLocal()
        partner = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.user_id == user_id,
            SalesPartnerDB.is_active == True
        ).first()
        
        if not partner:
            db.close()
            return {"status": "success", "data": {"is_partner": False}}
        
        result = {
            "is_partner": True,
            "max_purchases": partner.max_purchases,
            "used_purchases": partner.used_purchases,
            "remaining_purchases": partner.max_purchases - partner.used_purchases,
            "discount_percent": partner.discount_percent
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error checking sales partner: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sales/partners")
async def get_sales_partners():
    """Get all sales partners."""
    try:
        db = SessionLocal()
        partners = db.query(SalesPartnerDB).all()
        result = []
        for p in partners:
            result.append({
                "id": p.id,
                "user_id": p.user_id,
                "username": p.username,
                "max_purchases": p.max_purchases,
                "used_purchases": p.used_purchases,
                "remaining": p.max_purchases - p.used_purchases,
                "discount_percent": p.discount_percent,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None
            })
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting sales partners: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sales/partners")
async def create_sales_partner(request: Request):
    """Create a new sales partner."""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username")
        max_purchases = int(data.get("max_purchases", 10))
        discount_percent = int(data.get("discount_percent", 0))
        
        if not user_id:
            return {"status": "error", "message": "user_id الزامی است"}
        
        db = SessionLocal()
        
        existing = db.query(SalesPartnerDB).filter(SalesPartnerDB.user_id == user_id).first()
        if existing:
            db.close()
            return {"status": "error", "message": "این کاربر قبلاً همکار است"}
        
        new_partner = SalesPartnerDB(
            user_id=user_id,
            username=username,
            max_purchases=max_purchases,
            used_purchases=0,
            discount_percent=discount_percent,
            is_active=True
        )
        db.add(new_partner)
        db.commit()
        db.close()
        
        return {"status": "success", "message": "همکار با موفقیت اضافه شد"}
    except Exception as e:
        logger.error(f"Error creating sales partner: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.put("/api/sales/partners/{partner_id}")
async def update_sales_partner(partner_id: int, request: Request):
    """Update sales partner."""
    try:
        data = await request.json()
        db = SessionLocal()
        
        partner = db.query(SalesPartnerDB).filter(SalesPartnerDB.id == partner_id).first()
        if not partner:
            db.close()
            return {"status": "error", "message": "همکار پیدا نشد"}
        
        if "max_purchases" in data:
            partner.max_purchases = int(data["max_purchases"])
        if "discount_percent" in data:
            partner.discount_percent = int(data["discount_percent"])
        if "is_active" in data:
            partner.is_active = data["is_active"]
        
        db.commit()
        db.close()
        
        return {"status": "success", "message": "همکار با موفقیت ویرایش شد"}
    except Exception as e:
        logger.error(f"Error updating sales partner: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.delete("/api/sales/partners/{partner_id}")
async def delete_sales_partner(partner_id: int):
    """Delete sales partner."""
    try:
        db = SessionLocal()
        partner = db.query(SalesPartnerDB).filter(SalesPartnerDB.id == partner_id).first()
        if not partner:
            db.close()
            return {"status": "error", "message": "همکار پیدا نشد"}
        
        db.delete(partner)
        db.commit()
        db.close()
        
        return {"status": "success", "message": "همکار حذف شد"}
    except Exception as e:
        logger.error(f"Error deleting sales partner: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sales/requests")
async def get_sales_requests():
    """Get pending sales requests."""
    try:
        db = SessionLocal()
        requests = db.query(SalesRequestDB).filter(
            SalesRequestDB.status == "pending"
        ).order_by(SalesRequestDB.created_at.desc()).all()
        
        result = []
        for r in requests:
            result.append({
                "id": r.id,
                "user_id": r.user_id,
                "username": r.username,
                "first_name": r.first_name,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting sales requests: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sales/transactions/{user_id}")
async def get_sales_transactions(user_id: int):
    """Get sales transactions for a partner."""
    try:
        db = SessionLocal()
        transactions = db.query(SalesTransactionDB).filter(
            SalesTransactionDB.partner_user_id == user_id
        ).order_by(SalesTransactionDB.created_at.desc()).all()
        
        result = []
        for t in transactions:
            result.append({
                "id": t.id,
                "client_email": t.client_email,
                "service_name": t.service_name,
                "price": t.price,
                "original_price": t.original_price,
                "discount_percent": t.discount_percent,
                "transaction_type": t.transaction_type,
                "is_settled": t.is_settled,
                "created_at": t.created_at.isoformat() if t.created_at else None
            })
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting sales transactions: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sales/settlement/{user_id}")
async def get_sales_settlement(user_id: int):
    """Get settlement summary for a partner."""
    try:
        db = SessionLocal()
        
        # Unsettled transactions
        transactions = db.query(SalesTransactionDB).filter(
            SalesTransactionDB.partner_user_id == user_id,
            SalesTransactionDB.is_settled == False
        ).all()
        
        purchases = []
        renewals = []
        total = 0
        
        for t in transactions:
            item = {
                "id": t.id,
                "client_email": t.client_email,
                "service_name": t.service_name,
                "price": t.price,
                "original_price": t.original_price,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            
            if t.transaction_type == "purchase":
                purchases.append(item)
            else:
                renewals.append(item)
            
            total += t.price
        
        db.close()
        
        return {
            "status": "success",
            "data": {
                "purchases": purchases,
                "renewals": renewals,
                "purchase_count": len(purchases),
                "renewal_count": len(renewals),
                "total_amount": total
            }
        }
    except Exception as e:
        logger.error(f"Error getting settlement: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# SALES REQUEST APPROVE/REJECT API
# ==============================================

@router.post("/api/sales/requests/{request_id}/approve")
async def approve_sales_request(request_id: int, request: Request):
    """Approve a sales request and create partner."""
    try:
        data = await request.json()
        max_purchases = int(data.get("max_purchases", 10))
        discount_percent = int(data.get("discount_percent", 0))
        
        db = SessionLocal()
        
        sales_request = db.query(SalesRequestDB).filter(SalesRequestDB.id == request_id).first()
        if not sales_request:
            db.close()
            return {"status": "error", "message": "درخواست پیدا نشد"}
        
        # Create partner
        new_partner = SalesPartnerDB(
            user_id=sales_request.user_id,
            username=sales_request.username,
            max_purchases=max_purchases,
            used_purchases=0,
            discount_percent=discount_percent,
            is_active=True
        )
        db.add(new_partner)
        
        # Update request status
        sales_request.status = "approved"
        
        db.commit()
        db.close()
        
        # Notify user via Telegram
        try:
            from api.routes.webhook import application
            await application.bot.send_message(
                chat_id=sales_request.user_id,
                text="🎉 **درخواست همکاری شما تایید شد!**\n\n"
                     f"📊 محدودیت: {max_purchases} اکانت\n"
                     f"🎁 تخفیف: {discount_percent}%\n\n"
                     "از دکمه 'همکاری در فروش' در منوی اصلی استفاده کنید.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error notifying partner: {str(e)}")
        
        return {"status": "success", "message": "همکار با موفقیت تایید شد"}
    except Exception as e:
        logger.error(f"Error approving sales request: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sales/requests/{request_id}/reject")
async def reject_sales_request(request_id: int):
    """Reject a sales request."""
    try:
        db = SessionLocal()
        sales_request = db.query(SalesRequestDB).filter(SalesRequestDB.id == request_id).first()
        if not sales_request:
            db.close()
            return {"status": "error", "message": "درخواست پیدا نشد"}
        
        sales_request.status = "rejected"
        db.commit()
        db.close()
        
        return {"status": "success", "message": "درخواست رد شد"}
    except Exception as e:
        logger.error(f"Error rejecting sales request: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sales/create-account")
async def create_sales_account(request: Request):
    """Create account for sales partner without payment."""
    try:
        data = await request.json()
        partner_user_id = data.get("partner_user_id")
        service_id = data.get("service_id")
        price = data.get("price")
        original_price = data.get("original_price")
        discount_percent = data.get("discount_percent")
        transaction_type = data.get("transaction_type", "purchase")
        
        db = SessionLocal()
        
        # Check partner
        partner = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.user_id == partner_user_id,
            SalesPartnerDB.is_active == True
        ).first()
        
        if not partner:
            db.close()
            return {"status": "error", "message": "همکار پیدا نشد"}
        
        # Check remaining
        remaining = partner.max_purchases - partner.used_purchases
        if remaining <= 0:
            db.close()
            return {"status": "error", "message": "سقف خرید تکمیل شده"}
        
        # Get service
        service = db.query(ServiceDB).filter(ServiceDB.id == service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}
        
        # Get panel
        panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        # ====== Save info before closing session ======
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        panel_sub_url = panel.sub_url or ""
        panel_name = panel.name
        service_name = service.name
        service_volume = service.volume
        service_duration = service.duration
        service_inbound_id = service.inbound_id
        
        # Generate username
        email = await generate_username(partner_user_id)
        
        # Calculate volume
        if service_volume and service_volume != "unlimited":
            totalGB = int(service_volume) * 1073741824
        else:
            totalGB = 0
        
        # Calculate expiry
        duration_months = service_duration or 1
        expiry_time = int((datetime.now() + timedelta(days=duration_months * 30)).timestamp() * 1000)
        
        limit_ip = 3 if totalGB == 0 else 0
        
        # Get inbound IDs
        inbound_ids = []
        if service_inbound_id:
            try:
                inbound_ids = [int(service_inbound_id)]
            except:
                pass
        
        if not inbound_ids:
            db.close()
            return {"status": "error", "message": "Inbound پیدا نشد"}
        
        # Create subId
        import uuid
        client_sub_id = str(uuid.uuid4())
        
        # Prepare client data
        client_data = {
            "client": {
                "email": email,
                "totalGB": totalGB,
                "expiryTime": expiry_time,
                "tgId": partner_user_id,
                "limitIp": limit_ip,
                "enable": True,
                "subId": client_sub_id
            },
            "inboundIds": inbound_ids
        }
        
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }
        
        # Create in panel
        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/add",
                headers=headers,
                json=client_data
            )
            
            if response.status_code != 200:
                db.close()
                return {"status": "error", "message": "خطا در ساخت کاربر"}
            
            result = response.json()
            if not result.get("success"):
                db.close()
                return {"status": "error", "message": result.get("msg", "خطا")}
        
        # ====== Record transaction BEFORE commit ======
        transaction = SalesTransactionDB(
            partner_user_id=partner_user_id,
            client_email=email,
            service_id=service_id,
            service_name=service_name,
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
            transaction_type=transaction_type,
            is_settled=False
        )
        db.add(transaction)
        
        # Update partner used count
        partner.used_purchases += 1
        
        # ====== ✅ Save remaining BEFORE commit ======
        remaining_after = partner.max_purchases - partner.used_purchases
        
        db.commit()
        db.close()
        
        # ====== Build sub_url AFTER close ======
        sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else None
        
        return {
            "status": "success",
            "message": "اکانت ساخته شد",
            "data": {
                "client_email": email,
                "sub_url": sub_url,
                "panel_name": panel_name,
                "remaining_purchases": remaining_after  # ✅ استفاده از متغیر ذخیره شده
            }
        }
    except Exception as e:
        logger.error(f"Error creating sales account: {str(e)}")
        return {"status": "error", "message": str(e)}



@router.post("/api/sales/renew-account")
async def renew_sales_account(request: Request):
    """Renew account for sales partner without payment."""
    try:
        data = await request.json()
        partner_user_id = data.get("partner_user_id")
        service_id = data.get("service_id")
        price = data.get("price")
        original_price = data.get("original_price")
        discount_percent = data.get("discount_percent")
        user_info = data.get("user_info")

        db = SessionLocal()

        # Check partner
        partner = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.user_id == partner_user_id,
            SalesPartnerDB.is_active == True
        ).first()

        if not partner:
            db.close()
            return {"status": "error", "message": "همکار پیدا نشد"}

        # Check remaining
        remaining = partner.max_purchases - partner.used_purchases
        if remaining <= 0:
            db.close()
            return {"status": "error", "message": "سقف خرید تکمیل شده"}

        # Get service
        service = db.query(ServiceDB).filter(ServiceDB.id == service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}

        username = user_info.get('email')
        client_data = user_info.get('client', {})
        panel = user_info.get('panel', {})

        panel_url = panel.get('url', '').rstrip('/')
        panel_api_token = panel.get('api_token', '')

        # Calculate time
        current_expiry_time = client_data.get('expiryTime', 0)
        remaining_days = 0
        if current_expiry_time > 0:
            current_expiry_date = datetime.fromtimestamp(current_expiry_time / 1000)
            remaining_days = max(0, (current_expiry_date - datetime.now()).days)

        duration_months = service.duration or 1
        new_days = duration_months * 30
        total_days = remaining_days + new_days
        new_expiry_time = int((datetime.now() + timedelta(days=total_days)).timestamp() * 1000)

        # Calculate volume
        current_total_bytes = client_data.get('totalGB', 0)
        current_used_bytes = client_data.get('usedGB', 0)
        if current_used_bytes == 0:
            current_used_bytes = client_data.get('usedTraffic', 0)

        if current_total_bytes > 0:
            remaining_bytes = max(0, current_total_bytes - current_used_bytes)
            if service.volume and service.volume != "unlimited":
                new_volume_bytes = int(service.volume) * 1073741824
            else:
                new_volume_bytes = 0
            new_total_bytes = remaining_bytes + new_volume_bytes
        else:
            new_total_bytes = 0

        update_data = {
            "email": username,
            "totalGB": new_total_bytes,
            "expiryTime": new_expiry_time,
            "tgId": client_data.get('tgId', partner_user_id),
            "limitIp": client_data.get('limitIp', 0),
            "enable": True,
            "subId": client_data.get('subId', '')
        }

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/update/{username}",
                headers=headers,
                json=update_data
            )

            if response.status_code != 200:
                db.close()
                return {"status": "error", "message": "خطا در تمدید"}

            result = response.json()
            if not result.get("success"):
                db.close()
                return {"status": "error", "message": result.get("msg", "خطا")}

        # Record transaction
        transaction = SalesTransactionDB(
            partner_user_id=partner_user_id,
            client_email=username,
            service_id=service_id,
            service_name=service.name,
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
            transaction_type="renewal",
            is_settled=False
        )
        db.add(transaction)

        partner.used_purchases += 1
        remaining_after = partner.max_purchases - partner.used_purchases

        db.commit()
        db.close()

        return {
            "status": "success",
            "message": "تمدید انجام شد",
            "data": {
                "client_email": username,
                "remaining_purchases": remaining_after
            }
        }
    except Exception as e:
        logger.error(f"Error renewing sales account: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sales/toggle-account")
async def toggle_sales_account(request: Request):
    """Toggle account enable/disable for sales partner."""
    try:
        data = await request.json()
        partner_user_id = data.get("partner_user_id")
        client_email = data.get("client_email")
        enable = data.get("enable", True)
        
        # Check ownership
        db = SessionLocal()
        transaction = db.query(SalesTransactionDB).filter(
            SalesTransactionDB.partner_user_id == partner_user_id,
            SalesTransactionDB.client_email == client_email
        ).first()
        
        if not transaction:
            db.close()
            return {"status": "error", "message": "این کاربر در لیست شما نیست"}
        
        # Find panel
        service = db.query(ServiceDB).filter(ServiceDB.id == transaction.service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}
        
        panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}
        
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        
        db.close()
        
        # ====== ✅ Fix: Include email in update_data ======
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }
        
        update_data = {
            "email": client_email,  # ✅ email required
            "enable": enable
        }
        
        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/update/{client_email}",
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                return {"status": "error", "message": f"خطا در بروزرسانی: {response.text}"}
            
            result = response.json()
            if not result.get("success"):
                return {"status": "error", "message": result.get("msg", "خطا")}
        
        return {"status": "success", "message": "عملیات موفق"}
    except Exception as e:
        logger.error(f"Error toggling account: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sales/partners/{partner_id}/deactivate-all")
async def deactivate_all_partner_accounts(partner_id: int):
    """Deactivate all accounts of a partner."""
    try:
        db = SessionLocal()
        partner = db.query(SalesPartnerDB).filter(SalesPartnerDB.id == partner_id).first()

        if not partner:
            db.close()
            return {"status": "error", "message": "همکار پیدا نشد"}

        # Get all unsettled transactions
        transactions = db.query(SalesTransactionDB).filter(
            SalesTransactionDB.partner_user_id == partner.user_id,
            SalesTransactionDB.is_settled == False
        ).all()

        results = []
        success_count = 0
        failed_count = 0

        for t in transactions:
            try:
                # Find panel
                service = db.query(ServiceDB).filter(ServiceDB.id == t.service_id).first()
                if not service:
                    continue

                panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
                if not panel:
                    continue

                panel_url = panel.url.rstrip("/")
                panel_api_token = panel.api_token

                headers = {
                    "accept": "application/json",
                    "Authorization": f"Bearer {panel_api_token}",
                    "Content-Type": "application/json"
                }

                update_data = {
                    "email": t.client_email,
                    "enable": False
                }

                async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                    response = await http_client.post(
                        f"{panel_url}/panel/api/clients/update/{t.client_email}",
                        headers=headers,
                        json=update_data
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            success_count += 1
                            results.append({"email": t.client_email, "status": "success"})
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                failed_count += 1
                results.append({"email": t.client_email, "status": "error", "error": str(e)})

        db.close()

        return {
            "status": "success",
            "message": f"{success_count} اکانت غیرفعال شد، {failed_count} خطا",
            "data": {
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }
        }
    except Exception as e:
        logger.error(f"Error deactivating partner accounts: {str(e)}")
        return {"status": "error", "message": str(e)}



@router.post("/api/sales/settle-payment")
async def settle_sales_payment(request: Request):
    """Mark all transactions as settled and reset used_purchases."""
    try:
        data = await request.json()
        partner_user_id = data.get("partner_user_id")

        db = SessionLocal()

        # Mark transactions as settled
        db.query(SalesTransactionDB).filter(
            SalesTransactionDB.partner_user_id == partner_user_id,
            SalesTransactionDB.is_settled == False
        ).update({"is_settled": True})

        # Reset used_purchases
        partner = db.query(SalesPartnerDB).filter(
            SalesPartnerDB.user_id == partner_user_id
        ).first()

        if partner:
            partner.used_purchases = 0

        db.commit()
        db.close()

        return {"status": "success", "message": "تسویه انجام شد"}
    except Exception as e:
        logger.error(f"Error settling payment: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/sales/daily-reminder")
async def send_daily_reminder():
    """Send daily settlement reminder to all partners."""
    try:
        db = SessionLocal()
        partners = db.query(SalesPartnerDB).filter(SalesPartnerDB.is_active == True).all()

        for partner in partners:
            # Get unsettled transactions
            transactions = db.query(SalesTransactionDB).filter(
                SalesTransactionDB.partner_user_id == partner.user_id,
                SalesTransactionDB.is_settled == False
            ).all()

            if not transactions:
                continue

            total = sum(t.price for t in transactions)

            message = (
                f"📋 **یادآوری تسویه حساب**\n\n"
                f"🤝 سلام!\n"
                f"شما {len(transactions)} تراکنش تسویه نشده دارید.\n\n"
                f"📊 جمع کل: {total:,} تومان\n\n"
                f"لطفاً برای تسویه اقدام کنید."
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "💰 پرداخت تسویه",
                        callback_data=f"sales_settle_pay_{total}"
                    )
                ]
            ]

            try:
                from api.routes.webhook import application
                await application.bot.send_message(
                    chat_id=partner.user_id,
                    text=message,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"Reminder sent to partner {partner.user_id}")
            except Exception as e:
                logger.error(f"Error sending reminder to {partner.user_id}: {str(e)}")

        db.close()
        return {"status": "success", "message": "یادآوری ارسال شد"}
    except Exception as e:
        logger.error(f"Error sending reminders: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================
# MESSAGE SETTINGS API
# ==============================================

@router.get("/api/settings/messages")
async def get_message_settings():
    """Get message settings."""
    try:
        db = SessionLocal()
        setting = db.query(MessageSettingsDB).first()
        
        if not setting:
            setting = MessageSettingsDB(
                welcome_message="👋 سلام {first_name} عزیز!\nبه ربات مدیریت سرویس‌ها خوش آمدید.\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                support_message="🆘 **پشتیبانی**\n\nبرای ارتباط با تیم پشتیبانی:\n💬 تلگرام: @SupportBot\n⏰ ساعات پاسخگویی: ۹ صبح تا ۱۲ شب",
                help_message="❓ **راهنما**\n\n🔹 **وضعیت من**: نمایش وضعیت\n🔹 **خرید سرویس**: خرید جدید\n🔹 **تمدید سرویس**: تمدید فعلی\n🔹 **اکانت تست**: تست 24 ساعته\n🔹 **زیر مجموعه‌ها**: لینک رفرال\n🔹 **پشتیبانی**: ارتباط با ما"
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        
        result = {
            "welcome_message": setting.welcome_message or "",
            "support_message": setting.support_message or "",
            "help_message": setting.help_message or ""
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting message settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/messages")
async def save_message_settings(request: Request):
    """Save message settings."""
    try:
        data = await request.json()
        db = SessionLocal()
        
        setting = db.query(MessageSettingsDB).first()
        if not setting:
            setting = MessageSettingsDB()
            db.add(setting)
        
        setting.welcome_message = data.get("welcome_message", "")
        setting.support_message = data.get("support_message", "")
        setting.help_message = data.get("help_message", "")
        setting.updated_at = datetime.now()
        
        db.commit()
        db.close()
        
        return {"status": "success", "message": "تنظیمات پیام‌ها ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving message settings: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==============================================
# GIFT ACCOUNT SETTINGS API
# ==============================================

@router.get("/api/settings/gift-account")
async def get_gift_account_settings():
    """Get gift account settings."""
    try:
        db = SessionLocal()
        setting = db.query(GiftAccountSettingsDB).first()

        if not setting:
            setting = GiftAccountSettingsDB(
                is_enabled=False,
                panel_ids=[],
                volume_gb=10,
                duration_days=1,
                limit_ip=0,
                schedule_hour=12,
                schedule_minute=0,
                post_duration_minutes=30,
                post_message="🎁 **اکانت هدیه!**\n\n🔗 لینک سابسکریپشن:\n`{sub_url}`"
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)

        result = {
            "is_enabled": setting.is_enabled,
            "panel_ids": setting.panel_ids or [],
            "volume_gb": setting.volume_gb,
            "duration_days": setting.duration_days,
            "limit_ip": setting.limit_ip,
            "schedule_hour": setting.schedule_hour,
            "schedule_minute": setting.schedule_minute,
            "post_duration_minutes": setting.post_duration_minutes,
            "post_message": setting.post_message or ""
        }
        db.close()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error getting gift account settings: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/settings/gift-account")
async def save_gift_account_settings(request: Request):
    """Save gift account settings."""
    try:
        data = await request.json()
        db = SessionLocal()

        setting = db.query(GiftAccountSettingsDB).first()
        if not setting:
            setting = GiftAccountSettingsDB()
            db.add(setting)

        setting.is_enabled = data.get("is_enabled", False)
        setting.panel_ids = data.get("panel_ids", [])
        setting.volume_gb = int(data.get("volume_gb", 10))
        setting.duration_days = int(data.get("duration_days", 1))
        setting.limit_ip = int(data.get("limit_ip", 0))
        setting.schedule_hour = int(data.get("schedule_hour", 12))
        setting.schedule_minute = int(data.get("schedule_minute", 0))
        setting.post_duration_minutes = int(data.get("post_duration_minutes", 30))
        setting.post_message = data.get("post_message", "")
        setting.updated_at = datetime.now()

        db.commit()
        db.close()

        return {"status": "success", "message": "تنظیمات اکانت هدیه ذخیره شد"}
    except Exception as e:
        logger.error(f"Error saving gift account settings: {str(e)}")
        return {"status": "error", "message": str(e)}



# ==============================================
# GIFT ACCOUNT SEND/CLEANUP API
# ==============================================

@router.post("/api/gift-account/send")
async def send_gift_account():
    """Send gift account to channel."""
    try:
        db = SessionLocal()
        setting = db.query(GiftAccountSettingsDB).first()

        if not setting or not setting.is_enabled:
            db.close()
            return {"status": "error", "message": "اکانت هدیه غیرفعال است"}

        # Get channel settings
        channel = db.query(ChannelSettingsDB).first()
        if not channel or not channel.channel_chat_id:
            db.close()
            return {"status": "error", "message": "کانال تنظیم نشده است"}

        # Get panels
        if setting.panel_ids:
            panels = db.query(PanelDB).filter(PanelDB.id.in_(setting.panel_ids)).all()
        else:
            panels = db.query(PanelDB).filter(PanelDB.is_active == True).all()

        if not panels:
            db.close()
            return {"status": "error", "message": "پنلی پیدا نشد"}

        # Select panel (sequential rotation)
        panel_index = setting.current_panel_index % len(panels)
        panel = panels[panel_index]
        setting.current_panel_index += 1

        # Create account
        panel_url = panel.url.rstrip("/")
        panel_api_token = panel.api_token
        panel_sub_url = panel.sub_url or ""
        panel_name = panel.name

        import uuid
        import secrets
        import string

        # Generate username
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        client_email = f"gift_{datetime.now().strftime('%Y%m%d')}_{random_suffix}"
        client_sub_id = str(uuid.uuid4())

        # Calculate volume
        total_gb = setting.volume_gb * 1073741824

        # Calculate expiry
        expiry_time = int((datetime.now() + timedelta(days=setting.duration_days)).timestamp() * 1000)

        # Get inbound IDs
        inbound_ids = []
        if panel.inbound_ids:
            for inbound_id in panel.inbound_ids:
                try:
                    inbound_ids.append(int(inbound_id))
                except:
                    pass

        if not inbound_ids:
            db.close()
            return {"status": "error", "message": "Inbound پیدا نشد"}

        client_data = {
            "client": {
                "email": client_email,
                "totalGB": total_gb,
                "expiryTime": expiry_time,
                "tgId": 0,
                "limitIp": setting.limit_ip,
                "enable": True,
                "subId": client_sub_id
            },
            "inboundIds": inbound_ids
        }

        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel_api_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
            response = await http_client.post(
                f"{panel_url}/panel/api/clients/add",
                headers=headers,
                json=client_data
            )

            if response.status_code != 200:
                db.close()
                return {"status": "error", "message": "خطا در ساخت اکانت"}

            result = response.json()
            if not result.get("success"):
                db.close()
                return {"status": "error", "message": result.get("msg", "خطا")}

        # Build sub URL
        sub_url = f"{panel_sub_url.rstrip('/')}/{client_sub_id}" if panel_sub_url and client_sub_id else None

        # Build message
        message_text = setting.post_message.replace("{sub_url}", sub_url or "N/A")

        # Send to channel
        from api.routes.webhook import application

        sent_message = await application.bot.send_message(
            chat_id=channel.channel_chat_id,
            text=message_text,
            parse_mode="Markdown"
        )

        # Save gift account record
        gift_account = GiftAccountDB(
            client_email=client_email,
            client_sub_id=client_sub_id,
            panel_id=panel.id,
            panel_name=panel_name,
            channel_message_id=sent_message.message_id,
            volume_gb=setting.volume_gb,
            duration_days=setting.duration_days,
            expires_at=datetime.now() + timedelta(minutes=setting.post_duration_minutes)
        )
        db.add(gift_account)
        db.commit()
        db.close()

        return {
            "status": "success",
            "message": "اکانت هدیه ارسال شد",
            "data": {
                "client_email": client_email,
                "sub_url": sub_url,
                "panel_name": panel_name,
                "message_id": sent_message.message_id
            }
        }
    except Exception as e:
        logger.error(f"Error sending gift account: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/api/gift-account/cleanup")
async def cleanup_gift_accounts():
    """Delete expired gift accounts from channel and panel."""
    try:
        db = SessionLocal()
        channel = db.query(ChannelSettingsDB).first()

        if not channel:
            db.close()
            return {"status": "error", "message": "کانال تنظیم نشده"}

        now = datetime.now()
        expired_accounts = db.query(GiftAccountDB).filter(
            GiftAccountDB.is_deleted == False,
            GiftAccountDB.expires_at <= now
        ).all()

        from api.routes.webhook import application

        deleted_count = 0
        for account in expired_accounts:
            try:
                # Delete from channel
                if account.channel_message_id:
                    try:
                        await application.bot.delete_message(
                            chat_id=channel.channel_chat_id,
                            message_id=account.channel_message_id
                        )
                    except:
                        pass

                # Delete from panel
                panel = db.query(PanelDB).filter(PanelDB.id == account.panel_id).first()
                if panel:
                    panel_url = panel.url.rstrip("/")
                    headers = {
                        "accept": "application/json",
                        "Authorization": f"Bearer {panel.api_token}"
                    }

                    async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
                        await http_client.post(
                            f"{panel_url}/panel/api/clients/del/{account.client_email}?keepTraffic=0",
                            headers=headers,
                            data=""
                        )

                account.is_deleted = True
                account.deleted_at = datetime.now()
                deleted_count += 1

            except Exception as e:
                logger.error(f"Error deleting gift account {account.client_email}: {str(e)}")

        db.commit()
        db.close()

        return {
            "status": "success",
            "message": f"{deleted_count} اکانت هدیه حذف شد",
            "data": {"deleted_count": deleted_count}  # ✅ این اضافه بشه
        }
    except Exception as e:
        logger.error(f"Error cleaning gift accounts: {str(e)}")
        return {"status": "error", "message": str(e)}



