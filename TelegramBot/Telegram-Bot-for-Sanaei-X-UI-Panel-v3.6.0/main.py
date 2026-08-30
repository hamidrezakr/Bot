"""
Main entry point for the Telegram bot using FastAPI.
"""

import os
from contextlib import asynccontextmanager
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

# ==============================================
# IMPORT ADMIN ROUTES
# ==============================================
from admin.routes.admin_routes import router as admin_router
from pathlib import Path

import models.panel

from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import RedirectResponse
from admin.routes.auth_routes import router as auth_router


# ==============================================
# WEEKLY CLEANUP TASK
# ==============================================

async def weekly_test_account_cleanup():
    """
    Run test account cleanup every week.
    This function runs in background and cleans up expired test accounts.
    """
    while True:
        try:
            logger.info("🔄 Starting weekly test account cleanup...")
            
            # فراخوانی API پاکسازی
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
        
        # صبر تا هفته بعد (7 روز = 604800 ثانیه)
        # برای تست می‌تونی به 60 ثانیه تغییر بدی
        await asyncio.sleep(604800)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize the Telegram application
    await webhook.application.initialize()
    logger.info("Telegram application initialized")

    # Set webhook
    try:
        response = await webhook.set_webhook()
        logger.info(f"Webhook setup: {response}")
    except Exception as e:
        logger.error(f"Failed to set webhook on startup: {str(e)}")

    # ====== شروع زمان‌بندی پاکسازی هفتگی ======
    cleanup_task = asyncio.create_task(weekly_test_account_cleanup())
    logger.info("✅ Weekly test account cleanup task started")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # ====== لغو زمان‌بندی پاکسازی ======
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("✅ Weekly cleanup task cancelled")
    except Exception as e:
        logger.error(f"Error cancelling cleanup task: {str(e)}")

    # Delete webhook
    try:
        response = await webhook.delete_webhook()
        logger.info(f"Webhook deleted: {response}")
    except Exception as e:
        logger.error(f"Failed to delete webhook on shutdown: {str(e)}")

    # Shutdown the Telegram application
    await webhook.application.shutdown()
    logger.info("Telegram application shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Telegram Bot with FastAPI and Colored Buttons",
    lifespan=lifespan
)

# ==============================================
# SETUP TEMPLATES AND STATIC FILES
# ==============================================
# Setup templates directory for admin panel
templates_dir = Path(__file__).parent / "admin" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files directory
static_dir = Path(__file__).parent / "admin" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

receipts_dir = Path(__file__).parent / "receipts"
if receipts_dir.exists():
    app.mount("/receipts", StaticFiles(directory=str(receipts_dir)), name="receipts")
else:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/receipts", StaticFiles(directory=str(receipts_dir)), name="receipts")

# Add Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.ADMIN_SECRET_KEY,
    max_age=None,
    same_site="lax",
    https_only=False
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    """Check admin authentication for /admin/* routes."""
    path = request.url.path

    # Skip login page and API
    if path.startswith("/admin/login") or path.startswith("/admin/api/login"):
        return await call_next(request)

    # Check admin routes
    if path.startswith("/admin"):
        # Skip static files
        if path.startswith("/static") or path.startswith("/receipts"):
            return await call_next(request)

        token = request.cookies.get("admin_session", "")

        from admin.routes.auth_routes import verify_session_token

        if not verify_session_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

    return await call_next(request)

# ==============================================
# INCLUDE ROUTERS
# ==============================================

# Include Telegram webhook router
app.include_router(webhook.router, tags=["Telegram"])

# ==============================================
# INCLUDE ADMIN ROUTER
# ==============================================
app.include_router(admin_router, tags=["Admin Panel"])
# Include auth router
app.include_router(auth_router, tags=["Admin Auth"])
# ==============================================
# ROOT ENDPOINT
# ==============================================

@app.get("/")
async def root():
    """
    Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "status": "running",
        "admin_panel": "/admin/dashboard"
    }


# ==============================================
# MAIN ENTRY POINT
# ==============================================

if __name__ == "__main__":
    # Read host and port from environment variables or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=settings.DEBUG
    )

