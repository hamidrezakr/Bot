"""
Admin Authentication
Session-based authentication with CAPTCHA protection
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import os

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from core.config import settings

# ============ Session Configuration ============
SESSION_SECRET = settings.admin_session_secret or secrets.token_urlsafe(32)
SESSION_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

# ============ CAPTCHA Storage (in-memory for simplicity) ============
# در تولید از Redis یا دیتابیس استفاده کنید
_captcha_store = {}  # {captcha_id: {"text": "ABC123", "created_at": datetime}}


def get_session_secret() -> str:
    """Return session secret key"""
    return SESSION_SECRET


def verify_admin_password(password: str) -> bool:
    """Verify admin password from .env"""
    return password == settings.admin_password


def verify_admin_username(username: str) -> bool:
    """Verify admin username from .env"""
    return username == settings.admin_username


def generate_captcha() -> Tuple[str, str]:
    """
    Generate a CAPTCHA image and return text.
    Returns: (captcha_id, captcha_text)
    """
    import random
    import string
    
    # Generate random text (6 characters)
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Create a simple image using PIL
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    
    # Create image
    width, height = 200, 70
    image = Image.new('RGB', (width, height), color=(240, 248, 255))
    draw = ImageDraw.Draw(image)
    
    # Add noise (random dots)
    for _ in range(500):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    
    # Add random lines
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)), width=2)
    
    # Try to load a font
    try:
        # Try to use a default font
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        # Fallback to default
        font = ImageFont.load_default()
    
    # Draw text with random position and rotation
    for i, char in enumerate(captcha_text):
        x = 20 + i * 30 + random.randint(-5, 5)
        y = 10 + random.randint(-5, 5)
        color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
        draw.text((x, y), char, fill=color, font=font)
    
    # Apply a slight blur for security
    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # Save image to bytes
    import io
    img_bytes = io.BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # Generate captcha_id
    captcha_id = secrets.token_urlsafe(16)
    
    # Store captcha (valid for 5 minutes)
    _captcha_store[captcha_id] = {
        "text": captcha_text,
        "created_at": datetime.now()
    }
    
    # Clean old captchas (older than 5 minutes)
    _clean_old_captchas()
    
    return captcha_id, img_bytes


def _clean_old_captchas():
    """Remove CAPTCHAs older than 5 minutes"""
    now = datetime.now()
    expired = []
    for cid, data in _captcha_store.items():
        if (now - data["created_at"]).seconds > 300:  # 5 minutes
            expired.append(cid)
    for cid in expired:
        del _captcha_store[cid]


def verify_captcha(captcha_id: str, user_input: str) -> bool:
    """
    Verify CAPTCHA input.
    Returns True if correct, False otherwise.
    """
    if captcha_id not in _captcha_store:
        return False
    
    data = _captcha_store[captcha_id]
    
    # Check if expired (5 minutes)
    if (datetime.now() - data["created_at"]).seconds > 300:
        del _captcha_store[captcha_id]
        return False
    
    # Verify text (case-insensitive)
    result = user_input.upper() == data["text"].upper()
    
    # Remove used captcha
    del _captcha_store[captcha_id]
    
    return result


def authenticate_admin(username: str, password: str, captcha_id: str, captcha_input: str) -> bool:
    """
    Authenticate admin user with CAPTCHA.
    Returns True if successful, False otherwise.
    """
    # Check username
    if username != settings.admin_username:
        return False
    
    # Check password
    if password != settings.admin_password:
        return False
    
    # Check CAPTCHA
    if not verify_captcha(captcha_id, captcha_input):
        return False
    
    return True


async def get_current_admin(request: Request) -> Dict:
    """
    Dependency to get current admin from session.
    Used to protect admin routes.
    """
    admin = request.session.get("admin")
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"Location": "/admin/login"}
        )
    return admin


def is_admin_authenticated(request: Request) -> bool:
    """Check if admin is authenticated (for middleware)"""
    return request.session.get("admin") is not None


def create_admin_session(request: Request, username: str) -> None:
    """Create admin session"""
    request.session["admin"] = {
        "username": username,
        "login_time": datetime.now().isoformat()
    }


def destroy_admin_session(request: Request) -> None:
    """Destroy admin session"""
    request.session.clear()