"""
Panel service module for managing X-UI panel operations.
Handles communication with X-UI panels and database operations.
"""

import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from core.logging import logger
from models.panel import PanelDB, Panel, PanelStatus, InboundInfo
from core.exceptions import PanelError, PanelNotFoundError, PanelConnectionError, PanelAuthenticationError, PanelValidationError

class PanelService:
    """
    Service class for managing X-UI panels.
    Handles CRUD operations, health checks, and API communication.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize panel service with database session.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    async def create_panel(self, panel_data: Dict[str, Any]) -> PanelDB:
        """
        Create a new panel in the database.
        
        Args:
            panel_data: Dictionary containing panel configuration
        
        Returns:
            PanelDB: Created panel object
        
        Raises:
            PanelError: If validation fails or panel already exists
        """
        # Validate required fields
        if not panel_data.get("name"):
            raise PanelError("Panel name is required")
        if not panel_data.get("url"):
            raise PanelError("Panel URL is required")
        if not panel_data.get("api_token"):
            raise PanelError("API token is required")
        
        # Check for duplicate name
        existing = self.db.query(PanelDB).filter(
            PanelDB.name == panel_data["name"]
        ).first()
        if existing:
            raise PanelError(f"Panel with name '{panel_data['name']}' already exists")
        
        # Create new panel
        new_panel = PanelDB(
            name=panel_data["name"],
            url=panel_data["url"].rstrip("/"),
            api_token=panel_data["api_token"],
            sub_url=panel_data.get("sub_url"),
            inbound_ids=panel_data.get("inbound_ids", []),
            status="unknown",
            users_count=0,
            is_active=True
        )
        
        self.db.add(new_panel)
        self.db.commit()
        self.db.refresh(new_panel)
        
        logger.info(f"Panel created: {new_panel.name} (ID: {new_panel.id})")
        return new_panel
    
    async def update_panel(self, panel_id: int, panel_data: Dict[str, Any]) -> PanelDB:
        """
        Update an existing panel.
        
        Args:
            panel_id: ID of the panel to update
            panel_data: Dictionary with updated fields
        
        Returns:
            PanelDB: Updated panel object
        
        Raises:
            PanelError: If panel not found or validation fails
        """
        panel = self.db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            raise PanelError(f"Panel with ID {panel_id} not found")
        
        # Update fields
        if "name" in panel_data:
            panel.name = panel_data["name"]
        if "url" in panel_data:
            panel.url = panel_data["url"].rstrip("/")
        if "api_token" in panel_data:
            panel.api_token = panel_data["api_token"]
        if "sub_url" in panel_data:
            panel.sub_url = panel_data["sub_url"]
        if "inbound_ids" in panel_data:
            panel.inbound_ids = panel_data["inbound_ids"]
        if "is_active" in panel_data:
            panel.is_active = panel_data["is_active"]
        
        panel.updated_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(panel)
        
        logger.info(f"Panel updated: {panel.name} (ID: {panel.id})")
        return panel
    
    async def delete_panel(self, panel_id: int) -> bool:
        """
        Delete a panel from the database.
        
        Args:
            panel_id: ID of the panel to delete
        
        Returns:
            bool: True if deleted successfully
        
        Raises:
            PanelError: If panel not found
        """
        panel = self.db.query(PanelDB).filter(PanelDB.id == panel_id).first()
        if not panel:
            raise PanelError(f"Panel with ID {panel_id} not found")
        
        self.db.delete(panel)
        self.db.commit()
        
        logger.info(f"Panel deleted: ID {panel_id}")
        return True
    
    async def get_panel(self, panel_id: int) -> Optional[PanelDB]:
        """
        Get a panel by ID.
        
        Args:
            panel_id: Panel ID
        
        Returns:
            Optional[PanelDB]: Panel object or None
        """
        return self.db.query(PanelDB).filter(PanelDB.id == panel_id).first()
    
    async def get_all_panels(self) -> List[PanelDB]:
        """
        Get all panels from the database.
        
        Returns:
            List[PanelDB]: List of all panels
        """
        return self.db.query(PanelDB).all()
    
    async def check_panel_health(self, panel: PanelDB) -> PanelStatus:
        """
        Check the health status of a panel by calling its API.
        
        Args:
            panel: Panel object to check
        
        Returns:
            PanelStatus: Panel health status information
        
        Raises:
            PanelError: If API call fails
        """
        try:
            # Get server status
            status_data = await self._fetch_panel_status(panel)
            
            # Get clients list
            clients_data = await self._fetch_clients(panel)
            
            # Extract inbound information
            inbounds = await self._fetch_inbounds(panel)
            
            # Update panel with latest data
            panel.status = status_data.get("state", "unknown")
            panel.version = status_data.get("panelVersion")
            panel.total_sent = status_data.get("netTraffic", {}).get("sent", 0)
            panel.total_recv = status_data.get("netTraffic", {}).get("recv", 0)
            panel.users_count = len(clients_data)
            panel.last_check = datetime.now()
            
            # Update inbound IDs if available
            if inbounds:
                panel.inbound_ids = [str(inbound.get("id")) for inbound in inbounds if inbound.get("id")]
            
            self.db.commit()
            self.db.refresh(panel)
            
            logger.info(f"Panel health checked: {panel.name} - Status: {panel.status}")
            
            return PanelStatus(
                status=panel.status,
                version=panel.version or "Unknown",
                users_count=panel.users_count,
                total_sent=panel.total_sent,
                total_recv=panel.total_recv,
                last_check=panel.last_check
            )
            
        except Exception as e:
            logger.error(f"Error checking panel health for {panel.name}: {str(e)}")
            panel.status = "offline"
            panel.last_check = datetime.now()
            self.db.commit()
            raise PanelError(f"Failed to check panel health: {str(e)}")
    
    async def _fetch_panel_status(self, panel: PanelDB) -> Dict[str, Any]:
        """
        Fetch server status from X-UI panel.
        
        Args:
            panel: Panel object
        
        Returns:
            Dict[str, Any]: Server status data
        
        Raises:
            PanelError: If API call fails
        """
        url = f"{panel.url}/panel/api/server/status"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel.api_token}"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                raise PanelError("Connection failed - Panel is offline")
            except httpx.TimeoutException:
                raise PanelError("Connection timeout - Panel is not responding")
            except Exception as e:
                raise PanelError(f"API request failed: {str(e)}")
    
    async def _fetch_clients(self, panel: PanelDB) -> List[Dict[str, Any]]:
        """
        Fetch clients list from X-UI panel.
        
        Args:
            panel: Panel object
        
        Returns:
            List[Dict[str, Any]]: List of clients
        
        Raises:
            PanelError: If API call fails
        """
        url = f"{panel.url}/panel/api/clients/list"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel.api_token}"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data.get("clients", []) if isinstance(data, dict) else data
            except Exception as e:
                logger.warning(f"Failed to fetch clients for {panel.name}: {str(e)}")
                return []
    
    async def _fetch_inbounds(self, panel: PanelDB) -> List[Dict[str, Any]]:
        """
        Fetch inbounds list from X-UI panel.
        
        Args:
            panel: Panel object
        
        Returns:
            List[Dict[str, Any]]: List of inbounds
        
        Raises:
            PanelError: If API call fails
        """
        url = f"{panel.url}/panel/api/inbounds/list"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {panel.api_token}"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.warning(f"Failed to fetch inbounds for {panel.name}: {str(e)}")
                return []
    
    async def fetch_inbounds_async(self, url: str, token: str) -> List[InboundInfo]:
        """
        Fetch inbounds from a panel without saving to database.
        Used for preview during panel creation.
        
        Args:
            url: Panel URL
            token: API token
        
        Returns:
            List[InboundInfo]: List of inbound information
        
        Raises:
            PanelError: If API call fails
        """
        try:
            full_url = f"{url.rstrip('/')}/panel/api/inbounds/list"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {token}"
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(full_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                inbounds = []
                for inbound in data:
                    inbounds.append(InboundInfo(
                        id=inbound.get("id"),
                        remark=inbound.get("remark", ""),
                        port=inbound.get("port"),
                        protocol=inbound.get("protocol")
                    ))
                
                return inbounds
                
        except httpx.ConnectError:
            raise PanelError("Connection failed - Panel is offline")
        except httpx.TimeoutException:
            raise PanelError("Connection timeout - Panel is not responding")
        except Exception as e:
            raise PanelError(f"Failed to fetch inbounds: {str(e)}")
    
    async def get_panel_with_details(self, panel_id: int) -> Optional[Dict[str, Any]]:
        """
        Get panel with detailed information including status.
        
        Args:
            panel_id: Panel ID
        
        Returns:
            Optional[Dict[str, Any]]: Panel with details
        """
        panel = await self.get_panel(panel_id)
        if not panel:
            return None
        
        return {
            "id": panel.id,
            "name": panel.name,
            "url": panel.url,
            "sub_url": panel.sub_url,
            "inbound_ids": panel.inbound_ids or [],
            "status": panel.status,
            "version": panel.version,
            "users_count": panel.users_count,
            "total_sent": panel.total_sent,
            "total_recv": panel.total_recv,
            "last_check": panel.last_check.isoformat() if panel.last_check else None,
            "is_active": panel.is_active
        }
