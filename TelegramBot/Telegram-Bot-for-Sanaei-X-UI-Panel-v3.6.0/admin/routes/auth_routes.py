"""
Authentication routes for admin panel.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import secrets
import string
import time
import hashlib
from datetime import datetime, timedelta
from core.config import settings
from core.logging import logger

router = APIRouter(prefix="/admin", tags=["Admin Auth"])

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# ===== Rate Limiting =====
login_attempts = {}  # {ip: {"count": X, "locked_until": timestamp}}


def generate_captcha() -> tuple:
    """Generate random captcha text and session key."""
    chars = string.ascii_uppercase + string.digits
    captcha_text = ''.join(secrets.choice(chars) for _ in range(6))
    captcha_key = secrets.token_hex(16)
    return captcha_text, captcha_key


def create_session_token(username: str) -> str:
    """Create a session token."""
    expiry = datetime.now() + timedelta(hours=24)
    token_data = f"{username}:{expiry.timestamp()}:{settings.ADMIN_SECRET_KEY}"
    token = hashlib.sha256(token_data.encode()).hexdigest()
    return token


def verify_session_token(token: str) -> bool:
    """Verify session token."""
    if not token:
        return False
    # Simple check - in production use proper JWT
    # Here we just check if token exists in sessions
    return token in active_sessions


active_sessions = set()  # Store active session tokens


# ===== Login Page =====
@router.get("/login")
async def login_page(request: Request):
    """Login page."""
    captcha_text, captcha_key = generate_captcha()
    
    # Store captcha answer temporarily
    request.session["captcha_answer"] = captcha_text
    request.session["captcha_key"] = captcha_key
    
    # Check if IP is locked
    client_ip = request.client.host
    if client_ip in login_attempts:
        attempt = login_attempts[client_ip]
        if attempt["locked_until"] > time.time():
            remaining = int(attempt["locked_until"] - time.time())
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": f"شما قفل شده‌اید. {remaining} ثانیه دیگر صبر کنید.",
                "captcha_text": captcha_text,
                "captcha_key": captcha_key,
                "locked": True
            })
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "captcha_text": captcha_text,
        "captcha_key": captcha_key,
        "locked": False
    })


# ===== Login API =====
@router.post("/api/login")
async def api_login(request: Request):
    """Process login."""
    try:
        data = await request.json()
        username = data.get("username", "")
        password = data.get("password", "")
        captcha_input = data.get("captcha", "")
        captcha_key = data.get("captcha_key", "")
        
        client_ip = request.client.host
        
        # Check if locked
        if client_ip in login_attempts:
            attempt = login_attempts[client_ip]
            if attempt["locked_until"] > time.time():
                remaining = int(attempt["locked_until"] - time.time())
                return JSONResponse({
                    "status": "error",
                    "message": f"شما قفل شده‌اید. {remaining} ثانیه صبر کنید.",
                    "locked": True
                }, status_code=429)
        
        # Verify captcha
        captcha_answer = request.session.get("captcha_answer", "")
        if captcha_input.upper() != captcha_answer.upper():
            # Track failed attempt
            if client_ip not in login_attempts:
                login_attempts[client_ip] = {"count": 0, "locked_until": 0}
            login_attempts[client_ip]["count"] += 1
            
            if login_attempts[client_ip]["count"] >= 5:
                login_attempts[client_ip]["locked_until"] = time.time() + 900  # 15 minutes
                login_attempts[client_ip]["count"] = 0
                return JSONResponse({
                    "status": "error",
                    "message": "تعداد تلاش ناموفق زیاد بود. ۱۵ دقیقه قفل شدید."
                }, status_code=429)
            
            return JSONResponse({
                "status": "error",
                "message": "کپچا اشتباه است"
            }, status_code=400)
        
        # Verify credentials
        if username != settings.ADMIN_USERNAME or password != settings.ADMIN_PASSWORD:
            if client_ip not in login_attempts:
                login_attempts[client_ip] = {"count": 0, "locked_until": 0}
            login_attempts[client_ip]["count"] += 1
            
            if login_attempts[client_ip]["count"] >= 5:
                login_attempts[client_ip]["locked_until"] = time.time() + 900
                login_attempts[client_ip]["count"] = 0
                return JSONResponse({
                    "status": "error",
                    "message": "تعداد تلاش ناموفق زیاد بود. ۱۵ دقیقه قفل شدید."
                }, status_code=429)
            
            return JSONResponse({
                "status": "error",
                "message": "نام کاربری یا رمز عبور اشتباه است"
            }, status_code=401)
        
        # Success
        token = create_session_token(username)
        active_sessions.add(token)
        
        # Reset attempts
        login_attempts[client_ip] = {"count": 0, "locked_until": 0}
        
        # Set cookie (session cookie - expires when browser closes)
        response = JSONResponse({"status": "success", "message": "ورود موفق"})
        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=None  # Session cookie
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ===== Logout =====
@router.get("/logout")
async def logout(request: Request, response: Response):
    """Logout."""
    token = request.cookies.get("admin_session", "")
    if token in active_sessions:
        active_sessions.discard(token)
    
    response.delete_cookie("admin_session")
    return RedirectResponse(url="/admin/login", status_code=302)
