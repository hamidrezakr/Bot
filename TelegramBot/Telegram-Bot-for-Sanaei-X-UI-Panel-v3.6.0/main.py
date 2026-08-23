"""
Main entry point for the Telegram bot using FastAPI.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

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
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================
# INCLUDE ROUTERS
# ==============================================

# Include Telegram webhook router
app.include_router(webhook.router, tags=["Telegram"])

# ==============================================
# INCLUDE ADMIN ROUTER 
# ==============================================
app.include_router(admin_router, tags=["Admin Panel"])

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
