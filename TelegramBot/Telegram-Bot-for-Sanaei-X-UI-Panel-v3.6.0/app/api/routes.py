"""
FastAPI routes for webhook and health endpoints.
"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def root() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Telegram Bot for X-UI Panel",
        "version": "1.0.0"
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check for monitoring."""
    return {"status": "healthy"}