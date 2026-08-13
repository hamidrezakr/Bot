"""
Authentication API Endpoints
Session-based login with CAPTCHA protection
"""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel

from core.admin_auth import authenticate_admin, create_admin_session, destroy_admin_session

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str
    captcha_id: str
    captcha_input: str


class LoginResponse(BaseModel):
    """Login response model"""
    success: bool
    message: str


@router.post("/login")
async def login(request: Request, login_data: LoginRequest):
    """
    Admin login endpoint with CAPTCHA.
    Creates session on successful login.
    """
    # Authenticate with CAPTCHA
    is_authenticated = authenticate_admin(
        username=login_data.username,
        password=login_data.password,
        captcha_id=login_data.captcha_id,
        captcha_input=login_data.captcha_input
    )
    
    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username, password, or CAPTCHA"
        )
    
    # Create session
    create_admin_session(request, login_data.username)
    
    return {
        "success": True,
        "message": "Login successful",
        "redirect": "/admin/dashboard"
    }


@router.post("/logout")
async def logout(request: Request):
    """
    Logout endpoint - destroys session.
    """
    destroy_admin_session(request)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/verify")
async def verify_session(request: Request):
    """
    Verify if current session is valid.
    """
    admin = request.session.get("admin")
    if admin:
        return {
            "valid": True,
            "username": admin.get("username")
        }
    return {
        "valid": False,
        "message": "No active session"
    }