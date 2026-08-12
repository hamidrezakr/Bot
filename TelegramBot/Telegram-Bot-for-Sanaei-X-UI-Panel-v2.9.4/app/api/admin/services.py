# app/api/admin/services.py
import aiosqlite
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.models.database import (
    get_all_services, add_service, delete_service, get_service_by_id, DB_PATH
)

router = APIRouter()

class ServiceCreate(BaseModel):
    name: str
    traffic_gb: int
    price_toman: int
    expiry_days: int
    sort_order: int = 0


@router.get("/admin/api/services")
async def api_get_services():
    return await get_all_services()

@router.post("/admin/api/services")
async def api_add_service(service: ServiceCreate):
    await add_service(service.name, service.traffic_gb, service.price_toman, service.expiry_days, service.sort_order)
    return {"success": True}

@router.put("/admin/api/services/{service_id}")
async def api_update_service(service_id: int, request: Request):
    data = await request.json()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET name = ?, traffic_gb = ?, price_toman = ?, expiry_days = ?, sort_order = ? WHERE id = ?",
            (data.get('name'), data.get('traffic_gb'), data.get('price_toman'), data.get('expiry_days'), data.get('sort_order', 0), service_id)
        )
        await db.commit()
    return {"success": True}

@router.delete("/admin/api/services/{service_id}")
async def api_delete_service(service_id: int):
    await delete_service(service_id)
    return {"success": True}
