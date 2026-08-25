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
    payment_link = Column(String(255), nullable=True)
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
                "api_token": p.api_token[:10] + "..." if p.api_token and len(p.api_token) > 10 else p.api_token,
                "inbound_ids": p.inbound_ids or [],
                "inbound_details": p.inbound_details or [],  # NEW: return full details
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
                "payment_link": s.payment_link,
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
            payment_link=data.get("payment_link"),
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
        if "payment_link" in data:
            service.payment_link = data["payment_link"]
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
                "price": s.price,
                "payment_link": s.payment_link
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

        # Validate required fields
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
            status="pending"
        )

        db.add(new_receipt)
        db.commit()
        db.refresh(new_receipt)
        db.close()

        logger.info(f"Receipt created for user {data.get('user_id')} (ID: {new_receipt.id})")
        return {"status": "success", "message": "رسید با موفقیت ذخیره شد", "data": {"id": new_receipt.id}}
    except Exception as e:
        logger.error(f"Error creating receipt: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/api/receipts/{receipt_id}/approve")
async def approve_receipt(receipt_id: int):
    """
    Approve a receipt and create user in panel.
    """
    try:
        db = SessionLocal()
        receipt = db.query(ReceiptDB).filter(ReceiptDB.id == receipt_id).first()
        if not receipt:
            db.close()
            return {"status": "error", "message": "رسید پیدا نشد"}

        # Update receipt status
        receipt.status = "approved"
        receipt.processed_at = datetime.now()
        db.commit()

        # Get service details
        service = db.query(ServiceDB).filter(ServiceDB.id == receipt.service_id).first()
        if not service:
            db.close()
            return {"status": "error", "message": "سرویس پیدا نشد"}

        # Get panel details
        panel = db.query(PanelDB).filter(PanelDB.id == service.panel_id).first()
        if not panel:
            db.close()
            return {"status": "error", "message": "پنل پیدا نشد"}

        # ====== Create user in panel ======
        import secrets
        import string
        
        # Generate random email
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        email = f"user_{receipt.user_id}_{random_suffix}"
        
        # Calculate totalGB from volume
        volume_gb = service.volume
        if volume_gb and volume_gb != "unlimited":
            totalGB = int(volume_gb) * 1073741824  # Convert GB to bytes
        else:
            totalGB = 0  # Unlimited
        
        # Calculate expiry time (duration in months)
        duration_months = service.duration or 1
        expiry_time = int((datetime.now() + timedelta(days=duration_months * 30)).timestamp() * 1000)
        
        # Get inbound IDs
        inbound_ids = []
        if service.inbound_id:
            try:
                inbound_ids = [int(service.inbound_id)]
            except:
                inbound_ids = []
        
        if not inbound_ids:
            db.close()
            return {"status": "error", "message": "هیچ Inboundی برای این سرویس تعریف نشده است"}
        
        # Prepare client data
        client_data = {
            "client": {
                "email": email,
                "totalGB": totalGB,
                "expiryTime": expiry_time,
                "tgId": receipt.user_id,
                "limitIp": 0,
                "enable": True
            },
            "inboundIds": inbound_ids
        }
        
        # Send request to panel
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(
                f"{panel.url}/panel/api/clients/add",
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {panel.api_token}",
                    "Content-Type": "application/json"
                },
                json=client_data
            )
            
            if response.status_code != 200:
                db.close()
                return {"status": "error", "message": f"خطا در ساخت کاربر در پنل: {response.text}"}
            
            result = response.json()
            if not result.get("success"):
                db.close()
                return {"status": "error", "message": result.get("msg", "خطا در ساخت کاربر")}
        
        # Save client info to receipt
        receipt.client_email = email
        receipt.client_uuid = result.get("obj", {}).get("id")
        db.commit()
        db.close()

        return {
            "status": "success",
            "message": "رسید تأیید شد و کاربر در پنل ساخته شد",
            "data": {
                "client_email": email,
                "panel_url": panel.url,
                "sub_url": panel.sub_url
            }
        }
        
    except Exception as e:
        logger.error(f"Error approving receipt: {str(e)}")
        return {"status": "error", "message": str(e)}
