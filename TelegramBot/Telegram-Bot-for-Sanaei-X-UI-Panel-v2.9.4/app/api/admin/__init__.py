# app/api/admin/__init__.py
from fastapi import APIRouter
from app.api.admin.panels import router as panels_router
from app.api.admin.services import router as services_router
from app.api.admin.payment_links import router as payment_links_router
from app.api.admin.receipts import router as receipts_router
from app.api.admin.settings import router as settings_router
from app.api.admin.reports import router as reports_router

router = APIRouter()

router.include_router(panels_router)
router.include_router(services_router)
router.include_router(payment_links_router)
router.include_router(receipts_router)
router.include_router(settings_router)
router.include_router(reports_router)
