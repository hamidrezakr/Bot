
"""
Panels API Endpoints
CRUD operations for X-UI panels
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from core.admin_auth import get_current_admin
from models.panel import Panel, PanelCreate, PanelUpdate
from services.panel_service import PanelService

router = APIRouter(prefix="/api/panels", tags=["Panels API"])


class PanelResponse(BaseModel):
    id: int
    name: str
    url: str
    token: str
    status: str
    user_count: int
    created_at: str


@router.get("/", response_model=List[PanelResponse])
async def get_panels(
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Get all panels"""
    return await service.get_all()


@router.post("/", response_model=PanelResponse)
async def create_panel(
    panel_data: PanelCreate,
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Create a new panel"""
    return await service.create(panel_data)


@router.get("/{panel_id}", response_model=PanelResponse)
async def get_panel(
    panel_id: int,
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Get a specific panel"""
    panel = await service.get_by_id(panel_id)
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel


@router.put("/{panel_id}", response_model=PanelResponse)
async def update_panel(
    panel_id: int,
    panel_data: PanelUpdate,
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Update a panel"""
    panel = await service.update(panel_id, panel_data)
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel


@router.delete("/{panel_id}")
async def delete_panel(
    panel_id: int,
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Delete a panel"""
    success = await service.delete(panel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Panel not found")
    return {"success": True, "message": "Panel deleted successfully"}


@router.post("/{panel_id}/test")
async def test_panel_connection(
    panel_id: int,
    admin: dict = Depends(get_current_admin),
    service: PanelService = Depends(PanelService)
):
    """Test connection to a panel"""
    result = await service.test_connection(panel_id)
    return {"success": result, "message": "Connection test completed"}