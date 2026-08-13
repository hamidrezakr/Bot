"""
Reports API Endpoints
Provides chart data and statistics
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from typing import Dict, Any

from core.admin_auth import get_current_admin
from services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["Reports API"])


@router.get("/")
async def get_reports(
    period: str = Query("month", regex="^(week|month|year)$"),
    admin: dict = Depends(get_current_admin),
    service: ReportService = Depends(ReportService)
):
    """
    Get report data for charts
    period: week, month, or year
    """
    # Calculate date range
    end_date = datetime.now()
    
    if period == "week":
        start_date = end_date - timedelta(days=7)
        interval = "day"
    elif period == "month":
        start_date = end_date - timedelta(days=30)
        interval = "day"
    else:  # year
        start_date = end_date - timedelta(days=365)
        interval = "month"
    
    # Get data from service
    chart_data = await service.get_chart_data(start_date, end_date, interval)
    stats = await service.get_stats(start_date, end_date)
    
    return {
        "chart_data": chart_data,
        "stats": stats
    }