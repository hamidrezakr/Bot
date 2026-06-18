# app/models/schemas.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LoginRequest(BaseModel):
    """Login request payload for X-UI panel"""
    username: str
    password: str

class Client(BaseModel):
    """Client/User information schema"""
    email: str
    totalGB: Optional[int] = 0
    usedGB: Optional[int] = 0
    expiryTime: Optional[int] = 0
    enable: Optional[bool] = True
    comment: Optional[str] = ""
    uuid: Optional[str] = "" 
    
    @property
    def remaining_gb(self) -> float:
        """Calculate remaining traffic in GB"""
        if self.totalGB == 0:
            return float('inf')
        remaining = self.totalGB - self.usedGB
        return max(0, remaining)
    
    @property
    def expiry_date(self) -> Optional[datetime]:
        """Convert expiry timestamp to datetime"""
        if self.expiryTime and self.expiryTime > 0:
            return datetime.fromtimestamp(self.expiryTime / 1000)
        return None
    
    @property
    def is_expired(self) -> bool:
        """Check if client is expired"""
        if self.expiryTime == 0:
            return False
        return datetime.now().timestamp() * 1000 > self.expiryTime

class Inbound(BaseModel):
    """Inbound configuration schema"""
    id: int
    remark: str
    port: int
    protocol: str
    enable: bool
    clients: Optional[List[Client]] = []
    
class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    obj: Optional[dict] = None
    msg: Optional[str] = None
