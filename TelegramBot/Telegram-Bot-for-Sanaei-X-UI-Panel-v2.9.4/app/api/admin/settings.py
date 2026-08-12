# app/api/admin/settings.py
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.models.database import (
    get_help_settings, update_help_settings, get_warning_message, update_warning_message
)

router = APIRouter()

class HelpUpdate(BaseModel):
    description: str
    link: str
    install_link: str = ""


@router.get("/admin/api/help")
async def api_get_help():
    return await get_help_settings()

@router.post("/admin/api/help")
async def api_update_help(request: Request):
    data = await request.json()
    await update_help_settings(
        data.get('description', ''),
        data.get('link', ''),
        data.get('install_link', '')
    )
    return {"success": True}

@router.get("/admin/api/warning")
async def api_get_warning():
    message = await get_warning_message()
    return {"message": message}

@router.post("/admin/api/warning")
async def api_update_warning(request: Request):
    data = await request.json()
    await update_warning_message(data.get('description', ''))
    return {"success": True}
