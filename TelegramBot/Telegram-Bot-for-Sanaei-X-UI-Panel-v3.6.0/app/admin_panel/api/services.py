"""
Services API Endpoints
CRUD operations for services
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel

from core.admin_auth import get_current_admin
from services.service_service import ServiceService

router = APIRouter(prefix="/api/services", tags=["Services API"])


class ServiceCreate(BaseModel):
    name: str
    volume: int
    duration: int
    price: int
    status: str = "active"


class ServiceResponse(BaseModel):
    id: int
    name: str
    volume: int
    duration: int
    price: int
    status: str
    created_at: str


@router.get("/", response_model=List[ServiceResponse])
async def get_services(
    admin: dict = Depends(get_current_admin),
    service: ServiceService = Depends(ServiceService)
):
    """Get all services"""
    return await service.get_all()


@router.post("/", response_model=ServiceResponse)
async def create_service(
    service_data: ServiceCreate,
    admin: dict = Depends(get_current_admin),
    service: ServiceService = Depends(ServiceService)
):
    """Create a new service"""
    return await service.create(service_data)


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    service_data: ServiceCreate,
    admin: dict = Depends(get_current_admin),
    service: ServiceService = Depends(ServiceService)
):
    """Update a service"""
    updated = await service.update(service_id, service_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Service not found")
    return updated


@router.delete("/{service_id}")
async def delete_service(
    service_id: int,
    admin: dict = Depends(get_current_admin),
    service: ServiceService = Depends(ServiceService)
):
    """Delete a service"""
    success = await service.delete(service_id)
    if not success:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"success": True, "message": "Service deleted successfully"}