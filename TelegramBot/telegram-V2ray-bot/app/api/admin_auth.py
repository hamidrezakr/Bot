# app/api/admin_auth.py
import os
import hashlib
import secrets
import base64
from io import BytesIO
from captcha.image import ImageCaptcha
from fastapi import Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi import APIRouter
import random
import string

router = APIRouter()

# مسیر فایل اطلاعات ادمین
ADMIN_INFO_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "admin_panel.info")

# ذخیره موقت کپچاها در حافظه (تولید کننده، مقدار، زمان انقضا)
captcha_store = {}

def load_admin_credentials():
    """Load username and password from admin_panel.info file"""
    try:
        with open(ADMIN_INFO_FILE, 'r') as f:
            lines = f.readlines()
            username = None
            password = None
            for line in lines:
                if line.startswith('username:'):
                    username = line.split(':', 1)[1].strip()
                elif line.startswith('password:'):
                    password = line.split(':', 1)[1].strip()
            return username, password
    except Exception as e:
        print(f"Error loading admin credentials: {e}")
        return None, None

def generate_captcha():
    """Generate a CAPTCHA image and token"""
    # Create a random text (5 characters)
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    # Generate image
    image = ImageCaptcha(width=200, height=70)
    image_data = image.generate(captcha_text)
    
    # Convert to base64
    buffered = BytesIO()
    image.write(captcha_text, buffered)
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    # Create token for this CAPTCHA
    token = secrets.token_hex(16)
    captcha_store[token] = {
        "text": captcha_text,
        "expires": __import__('time').time() + 300  # 5 minutes expiry
    }
    
    return token, img_base64

def verify_captcha(token: str, user_input: str) -> bool:
    """Verify CAPTCHA token and user input"""
    if token not in captcha_store:
        return False
    
    captcha_data = captcha_store[token]
    
    # Check expiry
    if __import__('time').time() > captcha_data["expires"]:
        del captcha_store[token]
        return False
    
    # Verify text (case insensitive)
    result = captcha_data["text"].lower() == user_input.lower()
    
    # Remove used CAPTCHA
    del captcha_store[token]
    
    return result

def verify_admin_session(request: Request) -> bool:
    """Verify if user has valid admin session"""
    session_token = request.cookies.get("admin_session")
    if not session_token:
        return False
    
    # Simple session validation (store in memory)
    valid_sessions = getattr(verify_admin_session, "sessions", {})
    if session_token in valid_sessions:
        # Check expiry (24 hours)
        if __import__('time').time() < valid_sessions[session_token]:
            return True
        else:
            del valid_sessions[session_token]
    return False

def create_admin_session() -> str:
    """Create a new admin session token"""
    token = secrets.token_hex(32)
    sessions = getattr(verify_admin_session, "sessions", {})
    sessions[token] = __import__('time').time() + 86400  # 24 hours
    verify_admin_session.sessions = sessions
    return token

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page():
    """Show admin login page with CAPTCHA"""
    token, captcha_base64 = generate_captcha()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ورود به پنل مدیریت</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Tahoma', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .login-container {{
                background: white;
                border-radius: 20px;
                padding: 40px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h2 {{
                text-align: center;
                color: #667eea;
                margin-bottom: 30px;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #333;
            }}
            input {{
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 1rem;
                transition: all 0.3s;
            }}
            input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 5px rgba(102,126,234,0.3);
            }}
            .captcha-img {{
                text-align: center;
                margin: 15px 0;
                background: #f8f9fa;
                padding: 10px;
                border-radius: 8px;
            }}
            button {{
                width: 100%;
                background: #667eea;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.3s;
            }}
            button:hover {{
                background: #5a67d8;
            }}
            .error {{
                background: #f56565;
                color: white;
                padding: 10px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;
            }}
            .refresh-captcha {{
                text-align: center;
                margin-top: 10px;
            }}
            .refresh-captcha a {{
                color: #667eea;
                font-size: 0.9rem;
                cursor: pointer;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>🔐 ورود به پنل مدیریت</h2>
            <form id="loginForm" method="post" action="/admin/login">
                <div class="form-group">
                    <label>👤 نام کاربری</label>
                    <input type="text" name="username" required autocomplete="off">
                </div>
                <div class="form-group">
                    <label>🔒 رمز عبور</label>
                    <input type="password" name="password" required>
                </div>
                <div class="form-group">
                    <label>📷 کد امنیتی</label>
                    <div class="captcha-img">
                        <img src="data:image/png;base64,{captcha_base64}" alt="CAPTCHA" id="captchaImage">
                    </div>
                    <input type="text" name="captcha" placeholder="کد امنیتی را وارد کنید" required autocomplete="off">
                    <div class="refresh-captcha">
                        <a onclick="refreshCaptcha()">🔄 کد جدید</a>
                    </div>
                </div>
                <input type="hidden" name="captcha_token" value="{token}">
                <button type="submit">ورود به پنل</button>
            </form>
        </div>
        
        <script>
            function refreshCaptcha() {{
                fetch('/admin/refresh-captcha')
                    .then(response => response.json())
                    .then(data => {{
                        document.querySelector('input[name="captcha_token"]').value = data.token;
                        document.getElementById('captchaImage').src = "data:image/png;base64," + data.captcha;
                    }});
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.post("/admin/login")
async def admin_login_post(request: Request):
    """Handle login form submission"""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    captcha_input = form.get("captcha")
    captcha_token = form.get("captcha_token")
    
    # Load admin credentials
    admin_user, admin_pass = load_admin_credentials()
    
    # Verify CAPTCHA
    if not verify_captcha(captcha_token, captcha_input):
        return HTMLResponse(content="""
        <script>alert('❌ کد امنیتی اشتباه است!'); window.location.href='/admin/login';</script>
        """)
    
    # Verify credentials
    if username != admin_user or password != admin_pass:
        return HTMLResponse(content="""
        <script>alert('❌ نام کاربری یا رمز عبور اشتباه است!'); window.location.href='/admin/login';</script>
        """)
    
    # Create session
    session_token = create_admin_session()
    
    # Redirect to admin panel with session cookie
    response = HTMLResponse(content="""
    <script>window.location.href='/admin/dashboard';</script>
    """)
    response.set_cookie(key="admin_session", value=session_token, httponly=True, max_age=86400)
    return response

@router.get("/admin/refresh-captcha")
async def refresh_captcha():
    """Generate new CAPTCHA"""
    token, captcha_base64 = generate_captcha()
    return {"token": token, "captcha": captcha_base64}

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard - requires authentication"""
    if not verify_admin_session(request):
        return HTMLResponse(content="<script>window.location.href='/admin/login';</script>")
    
    # Serve the actual admin panel HTML
    from fastapi.responses import FileResponse
    import os
    admin_html = os.path.join(os.path.dirname(__file__), "..", "templates", "admin.html")
    if os.path.exists(admin_html):
        return FileResponse(admin_html)
    return HTMLResponse(content="<h1>Admin Panel</h1><p>Welcome to admin panel</p>")

@router.get("/admin/logout")
async def admin_logout():
    """Logout from admin panel"""
    response = HTMLResponse(content="<script>window.location.href='/admin/login';</script>")
    response.delete_cookie("admin_session")
    return response
