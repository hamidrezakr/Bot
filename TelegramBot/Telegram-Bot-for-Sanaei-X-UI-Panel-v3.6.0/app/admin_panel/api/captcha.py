"""
CAPTCHA API Endpoint
Generates and returns CAPTCHA image
"""

from fastapi import APIRouter, Response
from core.admin_auth import generate_captcha

router = APIRouter(prefix="/api/captcha", tags=["CAPTCHA"])


@router.get("/generate")
async def generate_captcha_image():
    """
    Generate a new CAPTCHA image.
    Returns the image and captcha_id in headers.
    """
    captcha_id, img_bytes = generate_captcha()
    
    # Create response with image
    response = Response(content=img_bytes.getvalue(), media_type="image/png")
    response.headers["X-Captcha-Id"] = captcha_id
    
    return response