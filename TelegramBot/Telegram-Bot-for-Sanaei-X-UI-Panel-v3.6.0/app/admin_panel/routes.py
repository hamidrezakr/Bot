"""
Admin Panel Routes
Serves HTML pages for the admin panel
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from core.admin_auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ============ Protected Routes (require login) ============

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show dashboard page"""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_tab": "dashboard",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/panels", response_class=HTMLResponse)
async def panels_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show panels management page"""
    return templates.TemplateResponse(
        "panels.html",
        {
            "request": request,
            "active_tab": "panels",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/services", response_class=HTMLResponse)
async def services_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show services management page"""
    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "active_tab": "services",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/payments", response_class=HTMLResponse)
async def payments_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show payment links page"""
    return templates.TemplateResponse(
        "payments.html",
        {
            "request": request,
            "active_tab": "payments",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/invoices", response_class=HTMLResponse)
async def invoices_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show invoices page"""
    return templates.TemplateResponse(
        "invoices.html",
        {
            "request": request,
            "active_tab": "invoices",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show reports page"""
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "active_tab": "reports",
            "admin_username": admin.get("username", "Admin")
        }
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    admin: dict = Depends(get_current_admin)
):
    """Show settings page"""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active_tab": "settings",
            "admin_username": admin.get("username", "Admin")
        }
    )


# ============ Public Routes (no login required) ============

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page - redirect to dashboard if already logged in"""
    from core.admin_auth import is_admin_authenticated
    
    if is_admin_authenticated(request):
        return RedirectResponse(url="/admin/dashboard")
    
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/logout")
async def logout(request: Request):
    """Logout - destroy session"""
    from core.admin_auth import destroy_admin_session
    
    destroy_admin_session(request)
    return RedirectResponse(url="/admin/login")