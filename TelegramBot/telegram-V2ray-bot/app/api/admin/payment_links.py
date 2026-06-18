# app/api/admin/payment_links.py
import aiosqlite
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.models.database import (
    get_all_payment_links, add_payment_link, delete_payment_link, update_payment_link_status, DB_PATH
)

router = APIRouter()

class PaymentLinkCreate(BaseModel):
    service_id: int
    service_name: str
    panel_id: int
    inbound_id: int
    link: str
    price_toman: int


@router.get("/admin/api/payment-links")
async def api_get_payment_links():
    return await get_all_payment_links()

@router.post("/admin/api/payment-links")
async def api_add_payment_link(link: PaymentLinkCreate):
    await add_payment_link(link.service_id, link.service_name, link.panel_id, link.inbound_id, link.link, link.price_toman)
    return {"success": True}

@router.put("/admin/api/payment-links/{link_id}")
async def api_update_payment_link(link_id: int, request: Request):
    data = await request.json()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payment_links SET service_id = ?, service_name = ?, panel_id = ?, inbound_id = ?, link = ?, price_toman = ? WHERE id = ?",
            (data.get('service_id'), data.get('service_name'), data.get('panel_id'), data.get('inbound_id'), data.get('link'), data.get('price_toman'), link_id)
        )
        await db.commit()
    return {"success": True}

@router.delete("/admin/api/payment-links/{link_id}")
async def api_delete_payment_link(link_id: int):
    await delete_payment_link(link_id)
    return {"success": True}

@router.post("/admin/api/payment-links/{link_id}/toggle")
async def api_toggle_payment_link(link_id: int, request: Request):
    data = await request.json()
    is_active = data.get('is_active', True)
    await update_payment_link_status(link_id, is_active)
    return {"success": True}
