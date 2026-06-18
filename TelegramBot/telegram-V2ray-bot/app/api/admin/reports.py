# app/api/admin/reports.py
from fastapi import APIRouter
from typing import Optional

from app.models.database import get_stats, get_transactions, get_transactions_count

router = APIRouter()


@router.get("/admin/api/reports/stats")
async def api_get_stats(period: str = "daily"):
    """Get statistics for dashboard"""
    return await get_stats(period)

@router.get("/admin/api/reports/transactions")
async def api_get_transactions(
    page: int = 1,
    limit: int = 50,
    status: str = None,
    type: str = None
):
    """Get transaction history with pagination"""
    offset = (page - 1) * limit
    transactions = await get_transactions(limit, offset, status, type)
    total = await get_transactions_count(status, type)

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 1
    }
