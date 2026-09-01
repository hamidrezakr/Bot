"""
Main entry point for the Telegram bot using FastAPI.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime  
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
import httpx

from core.config import settings
from core.logging import logger
from api.routes import webhook

from admin.routes.admin_routes import router as admin_router
from pathlib import Path
import models.panel
from fastapi import Request
from fastapi.responses import RedirectResponse
from admin.routes.auth_routes import router as auth_router


async def gift_account_scheduler():
    """Check every minute for gift account scheduling and cleanup."""
    last_sent_date = None
    
    logger.info("🎁 Gift account scheduler started")  

    while True:
        try:
            # ====== ۱. Cleanup ======
            logger.info("🔄 Running gift cleanup check...")  
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    cleanup_response = await client.post(
                        "http://localhost:8000/admin/api/gift-account/cleanup"
                    )
                    logger.info(f"Cleanup HTTP: {cleanup_response.status_code}")  
                    
                    if cleanup_response.status_code == 200:
                        cleanup_result = cleanup_response.json()
                        deleted = cleanup_result.get("data", {}).get("deleted_count", 0)
                        logger.info(f"Cleanup deleted: {deleted}")
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")  
            
            
            try:
                now = datetime.now()
                if last_sent_date != now.date():
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(
                            "http://localhost:8000/admin/api/settings/gift-account"
                        )
                        settings_data = response.json().get("data", {})
                    
                    if settings_data.get("is_enabled"):
                        schedule_hour = settings_data.get("schedule_hour", 12)
                        schedule_minute = settings_data.get("schedule_minute", 0)
                        
                        if now.hour == schedule_hour and now.minute == schedule_minute:
                            async with httpx.AsyncClient(timeout=60.0) as client:
                                send_response = await client.post(
                                    "http://localhost:8000/admin/api/gift-account/send"
                                )
                                logger.info(f"Gift sent: {send_response.json()}")
                            last_sent_date = now.date()
            except Exception as e:
                logger.error(f"Send error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")

        await asyncio.sleep(60)

# ===== WEEKLY CLEANUP =====
async def weekly_test_account_cleanup():
    while True:
        try:
            logger.info("🔄 Starting weekly test account cleanup...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "http://localhost:8000/admin/api/test-accounts/cleanup"
                )
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Cleanup result: {result.get('message')}")
                else:
                    logger.error(f"❌ Cleanup failed: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error in weekly cleanup: {str(e)}")
        await asyncio.sleep(604800)

# ===== DAILY SALES REMINDER =====
async def daily_sales_reminder():
    while True:
        try:
            now = datetime.now()
            end_of_day = datetime(now.year, now.month, now.day, 23, 59, 0)
            wait_seconds = (end_of_day - now).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "http://localhost:8000/admin/api/sales/daily-reminder"
                )
                logger.info(f"Daily reminder sent: {response.status_code}")
            await asyncio.sleep(86400)
        except Exception as e:
            logger.error(f"Error in daily reminder: {str(e)}")
            await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await webhook.application.initialize()
    logger.info("Telegram application initialized")
    try:
        response = await webhook.set_webhook()
        logger.info(f"Webhook setup: {response}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {str(e)}")

    # ✅ شروع تسک‌ها - هر دو قبل از yield
    cleanup_task = asyncio.create_task(weekly_test_account_cleanup())
    logger.info("✅ Weekly cleanup task started")
    
    reminder_task = asyncio.create_task(daily_sales_reminder())
    logger.info("✅ Daily reminder task started")
    
    gift_task = asyncio.create_task(gift_account_scheduler())
    logger.info("🎁 Gift account scheduler started")

    yield
    

    # Shutdown
    logger.info("Shutting down...")
    
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass

    try:
        response = await webhook.delete_webhook()
        logger.info(f"Webhook deleted: {response}")
    except Exception as e:
        logger.error(f"Failed to delete webhook: {str(e)}")

    await webhook.application.shutdown()
    logger.info("Telegram application shut down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Telegram Bot with FastAPI",
    lifespan=lifespan
)

# Templates & Static
templates_dir = Path(__file__).parent / "admin" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

static_dir = Path(__file__).parent / "admin" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

receipts_dir = Path(__file__).parent / "receipts"
if receipts_dir.exists():
    app.mount("/receipts", StaticFiles(directory=str(receipts_dir)), name="receipts")

# Middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.ADMIN_SECRET_KEY,
    max_age=None,
    same_site="lax",
    https_only=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    path = request.url.path
    protected_pages = [
        "/admin/dashboard",
        "/admin/panels",
        "/admin/categories",
        "/admin/services",
        "/admin/receipts",
        "/admin/reports",
        "/admin/staff",
        "/admin/settings",
        "/admin/broadcast",
    ]
    if path in protected_pages:
        token = request.cookies.get("admin_session", "")
        from admin.routes.auth_routes import verify_session_token
        if not verify_session_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)
    return await call_next(request)

# Routers
app.include_router(webhook.router, tags=["Telegram"])
app.include_router(admin_router, tags=["Admin Panel"])
app.include_router(auth_router, tags=["Admin Auth"])

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "status": "running",
        "admin_panel": "/admin/dashboard"
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=settings.DEBUG)
