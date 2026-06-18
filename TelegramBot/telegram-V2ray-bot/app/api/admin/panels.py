# app/api/admin/panels.py
import json
import aiosqlite
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.models.database import (
    get_all_panels, add_panel, delete_panel, get_panel_by_id,
    update_panel_show_status, update_panel_inbounds, get_panel_inbounds,
    update_panel_max_slots, get_active_users_count, DB_PATH
)

router = APIRouter()

class PanelCreate(BaseModel):
    name: str
    url: str
    username: str
    password: str
    max_slots: int = 0
    sub_url: str = ""


@router.get("/admin/api/panels")
async def api_get_panels():
    return await get_all_panels()

@router.get("/admin/api/panels/{panel_id}")
async def api_get_panel(panel_id: int):
    panel = await get_panel_by_id(panel_id)
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel

@router.post("/admin/api/panels")
async def api_add_panel(panel: PanelCreate):
    clean_url = panel.url.rstrip('/')
    clean_sub_url = panel.sub_url.rstrip('/') if panel.sub_url else ''
    await add_panel(panel.name, clean_url, panel.username, panel.password, True, '[]', panel.max_slots, clean_sub_url)
    return {"success": True}

@router.put("/admin/api/panels/{panel_id}")
async def api_update_panel(panel_id: int, request: Request):
    data = await request.json()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE panels SET name = ?, url = ?, username = ?, password = ?, sub_url = ? WHERE id = ?",
            (data.get('name'), data.get('url'), data.get('username'), data.get('password'), data.get('sub_url', ''), panel_id)
        )
        await db.commit()
    return {"success": True}

@router.delete("/admin/api/panels/{panel_id}")
async def api_delete_panel(panel_id: int):
    await delete_panel(panel_id)
    return {"success": True}

@router.post("/admin/api/panels/{panel_id}/toggle")
async def api_toggle_panel(panel_id: int, request: Request):
    data = await request.json()
    show_in_bot = data.get('show_in_bot', True)
    await update_panel_show_status(panel_id, show_in_bot)
    return {"success": True}

@router.post("/admin/api/panels/{panel_id}/max_slots")
async def api_update_max_slots(panel_id: int, request: Request):
    data = await request.json()
    max_slots = data.get('max_slots', 0)
    await update_panel_max_slots(panel_id, max_slots)
    return {"success": True}

@router.get("/admin/api/panels/{panel_id}/inbounds")
async def api_get_panel_inbounds(panel_id: int):
    panel = await get_panel_by_id(panel_id)
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    selected = json.loads(panel.get('selected_inbounds', '[]'))
    inbounds = await get_panel_inbounds(panel_id)
    return {"inbounds": inbounds, "selected": selected}

@router.post("/admin/api/panels/{panel_id}/inbounds")
async def api_update_panel_inbounds(panel_id: int, request: Request):
    data = await request.json()
    selected_inbounds = data.get('selected_inbounds', [])
    await update_panel_inbounds(panel_id, selected_inbounds)
    return {"success": True}

@router.get("/admin/api/panels/{panel_id}/active_count")
async def api_get_active_count(panel_id: int):
    panel = await get_panel_by_id(panel_id)
    if not panel:
        return {"count": 0}
    selected_ids = json.loads(panel.get('selected_inbounds', '[]'))
    total_active = 0
    for inbound_id in selected_ids:
        total_active += await get_active_users_count(panel_id, inbound_id)
    return {"count": total_active}
