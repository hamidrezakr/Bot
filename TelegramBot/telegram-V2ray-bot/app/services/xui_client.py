# app/services/xui_client.py
import httpx
import logging
import time
import json
from typing import Optional, List
from app.models.schemas import Client, Inbound

logger = logging.getLogger(__name__)

class XUIClient:
    def __init__(self, base_url: str = None, username: str = None, password: str = None):
        from app.config import PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD
        self.base_url = (base_url or PANEL_URL).rstrip('/')
        self.username = username or PANEL_USERNAME
        self.password = password or PANEL_PASSWORD
        self.client = httpx.AsyncClient(verify=False, timeout=30.0)
        self.is_logged_in = False

    async def login(self) -> bool:
        try:
            login_url = f"{self.base_url}/login"
            logger.info(f"Logging in to: {login_url}")

            payload = {
                "username": self.username,
                "password": self.password
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            response = await self.client.post(login_url, json=payload, headers=headers)
            logger.info(f"Login response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.is_logged_in = True
                    logger.info("X-UI panel login successful")
                    return True

            logger.error(f"Login failed: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def get_inbounds(self) -> Optional[List[Inbound]]:
        if not self.is_logged_in and not await self.login():
            logger.error("Cannot get inbounds: login failed")
            return None

        try:
            url = f"{self.base_url}/panel/api/inbounds/list"
            logger.info(f"Fetching inbounds from: {url}")

            response = await self.client.get(url)
            logger.info(f"Inbounds response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if data.get("success") and data.get("obj"):
                    inbounds_data = data.get("obj", [])
                    inbounds = []

                    for item in inbounds_data:
                        clients = []
                        for client_stat in item.get("clientStats", []):
                            client = Client(
                                email=client_stat.get("email", ""),
                                totalGB=client_stat.get("total", 0) // (1024**3) if client_stat.get("total") else 0,
                                usedGB=(client_stat.get("up", 0) + client_stat.get("down", 0)) // (1024**3),
                                expiryTime=client_stat.get("expiryTime", 0),
                                enable=client_stat.get("enable", True),
                                comment="",
                                uuid=str(client_stat.get("id", ""))
                            )
                            clients.append(client)

                        inbound = Inbound(
                            id=item.get("id"),
                            remark=item.get("remark", "Unknown"),
                            port=item.get("port", 0),
                            protocol=item.get("protocol", "unknown"),
                            enable=item.get("enable", True),
                            clients=clients
                        )
                        inbounds.append(inbound)

                    logger.info(f"Retrieved {len(inbounds)} inbounds")
                    return inbounds
                else:
                    logger.warning("No inbounds found")
                    return []
            else:
                logger.error(f"Failed to get inbounds: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Get inbounds error: {e}")
            return None

    async def get_client(self, email: str) -> Optional[Client]:
        if not self.is_logged_in and not await self.login():
            return None

        try:
            inbounds = await self.get_inbounds()
            if not inbounds:
                return None

            for inbound in inbounds:
                for client in inbound.clients:
                    if client.email.lower() == email.lower():
                        logger.info(f"Found client {email}")
                        return client

            logger.warning(f"Client {email} not found")
            return None

        except Exception as e:
            logger.error(f"Get client error: {e}")
            return None

    async def add_client(self, inbound_id: int, email: str, total_gb: int, expiry_days: int, limit_ip: int = 1) -> bool:
        """Add a new client to inbound"""
        if not self.is_logged_in and not await self.login():
            logger.error("Cannot add client: login failed")
            return False

        try:
            expiry_time = 0
            if expiry_days > 0:
                expiry_time = int((time.time() + expiry_days * 86400) * 1000)

            # Generate new UUID for client
            import uuid
            client_uuid = str(uuid.uuid4())

            # Format client data as JSON string for settings
            client_data = {
                "clients": [{
                    "id": client_uuid,
                    "email": email,
                    "totalGB": total_gb,
                    "expiryTime": expiry_time,
                    "limitIp": limit_ip,
                    "enable": True
                }]
            }

            # Convert settings to JSON string
            settings_json = json.dumps(client_data)

            payload = {
                "id": inbound_id,
                "settings": settings_json
            }

            headers = {"Content-Type": "application/json"}

            endpoints = [
                f"{self.base_url}/panel/api/inbounds/addClient",
                f"{self.base_url}/panel/inbound/addClient",
            ]

            for endpoint in endpoints:
                logger.info(f"Trying to add client to: {endpoint}")
                response = await self.client.post(endpoint, json=payload, headers=headers)
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response body: {response.text[:200]}")

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info(f"Client {email} added successfully to inbound {inbound_id}")
                        return True
                    else:
                        logger.warning(f"Response not success: {result.get('msg')}")
                elif response.status_code == 301:
                    continue
                else:
                    logger.warning(f"Failed with status {response.status_code}")

            logger.error("All endpoints failed to add client")
            return False

        except Exception as e:
            logger.error(f"Add client error: {e}")
            return False

    async def update_client(self, inbound_id: int, user_uuid: str, email: str, 
                            new_total_bytes: int, new_expiry_time: int) -> bool:
        """
        Update existing client in panel
        """
        if not self.is_logged_in and not await self.login():
            logger.error("Cannot update client: login failed")
            return False

        try:
            # Build client data
            client_data = {
                "clients": [{
                    "id": user_uuid,
                    "email": email,
                    "totalGB": new_total_bytes,
                    "expiryTime": new_expiry_time,
                    "limitIp": 1,
                    "enable": True
                }]
            }
            
            settings_json = json.dumps(client_data)
            data_body = f"id={inbound_id}&settings={settings_json}"
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            url = f"{self.base_url}/panel/api/inbounds/updateClient/{user_uuid}"
            logger.info(f"Updating client at: {url}")
            logger.info(f"Data body: {data_body}")
            
            response = await self.client.post(url, content=data_body, headers=headers)
            logger.info(f"Update response: {response.status_code} - {response.text[:200]}")
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
            return False
            
        except Exception as e:
            logger.error(f"Update client error: {e}")
            return False

    async def reset_client_traffic(self, email: str) -> bool:
        """
        Reset traffic usage for a client
        Endpoint: POST /panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}
        """
        if not self.is_logged_in and not await self.login():
            logger.error("Cannot reset traffic: login failed")
            return False
        
        try:
            # First, find which inbound this client belongs to
            inbounds = await self.get_inbounds()
            inbound_id = None
            
            if inbounds:
                for inbound in inbounds:
                    for client in inbound.clients:
                        if client.email.lower() == email.lower():
                            inbound_id = inbound.id
                            break
                    if inbound_id:
                        break
            
            if not inbound_id:
                logger.error(f"Cannot find inbound for client {email}")
                return False
            
            # Reset traffic using the correct endpoint
            url = f"{self.base_url}/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            logger.info(f"Resetting traffic for {email} at: {url}")
            
            response = await self.client.post(url, headers=headers)
            logger.info(f"Reset traffic response status: {response.status_code}")
            logger.info(f"Reset traffic response body: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"Traffic reset successfully for {email}")
                    return True
                else:
                    logger.error(f"Reset API returned error: {result.get('msg')}")
                    return False
            else:
                logger.error(f"Reset failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Reset traffic error: {e}")
            return False

    async def get_all_clients(self) -> List[Client]:
        if not self.is_logged_in and not await self.login():
            return []

        all_clients = []
        inbounds = await self.get_inbounds()

        if inbounds:
            for inbound in inbounds:
                all_clients.extend(inbound.clients)

        return all_clients

    async def close(self):
        await self.client.aclose()


_xui_client = None

def get_xui_client():
    global _xui_client
    if _xui_client is None:
        _xui_client = XUIClient()
    return _xui_client
