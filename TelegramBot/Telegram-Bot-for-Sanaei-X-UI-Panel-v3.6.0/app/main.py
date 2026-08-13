"""
Main entry point for the Telegram Bot for X-UI Panel.
"""

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.session import SessionMiddleware
from pathlib import Path

from core.config import settings
from core.admin_auth import get_session_secret

# ============ Import Routes ============
from bot.handlers import get_handlers
from api.routes import router as api_router

# Admin Panel Routes
from admin_panel.routes import router as admin_router
from admin_panel.api.auth import router as auth_router
from admin_panel.api.captcha import router as captcha_router
from admin_panel.api.panels import router as panels_api_router
from admin_panel.api.services import router as services_api_router
from admin_panel.api.payments import router as payments_api_router
from admin_panel.api.invoices import router as invoices_api_router
from admin_panel.api.reports import router as reports_api_router
from admin_panel.api.settings import router as settings_api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Telegram Bot for X-UI Panel",
        description="Manage your X-UI panel users via Telegram bot",
        version="3.6.0",
        debug=settings.debug
    )
    
    # ============ Session Middleware ============
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_session_secret(),
        max_age=60 * 60 * 24 * 30,  # 30 days
        same_site="lax",
        https_only=False,  # Set to True in production with HTTPS
    )
    
    # ============ Include Routers ============
    # API routes
    app.include_router(api_router)
    
    # Admin panel routes (HTML pages)
    app.include_router(admin_router)
    
    # Admin panel API routes
    app.include_router(auth_router)
    app.include_router(captcha_router)
    app.include_router(panels_api_router)
    app.include_router(services_api_router)
    app.include_router(payments_api_router)
    app.include_router(invoices_api_router)
    app.include_router(reports_api_router)
    app.include_router(settings_api_router)
    
    # ============ Mount Static Files ============
    static_dir = Path(__file__).parent / "admin_panel" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    return app


def create_bot():
    """Create and configure Telegram bot application."""
    from telegram.ext import ApplicationBuilder
    
    application = ApplicationBuilder().token(settings.bot_token).build()
    
    # Register all handlers
    for handler in get_handlers():
        application.add_handler(handler)
    
    return application


# Create instances
app = create_app()
bot = create_bot()


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("🚀 Starting Telegram Bot for X-UI Panel")
    logger.info(f"👤 Admin username: {settings.admin_username}")
    
    try:
        await bot.initialize()
        await bot.start()
        logger.info(f"✅ Bot @{bot.bot.username} started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("🛑 Shutting down...")
    try:
        await bot.shutdown()
        logger.info("✅ Bot stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping bot: {e}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 Starting server on {settings.host}:{settings.port}")
    logger.info(f"📊 Admin panel: http://{settings.host}:{settings.port}/admin/login")
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )