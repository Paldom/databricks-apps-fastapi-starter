from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import ConfigDict

from app.api.common.schemas import ApiModel
from app.core.deps import get_current_user
from app.models.user_dto import CurrentUser

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "totalRevenue": 125000,
                "subscriptions": 1234,
                "sales": 5678,
                "activeUsers": 2345,
            }
        }
    )

    total_revenue: float
    subscriptions: float
    sales: float
    active_users: float


class ChartDataPoint(ApiModel):
    name: str
    value: float


@router.get(
    "/stats",
    operation_id="getDashboardStats",
    response_model=DashboardStats,
)
async def get_dashboard_stats(
    user: CurrentUser = Depends(get_current_user),
) -> DashboardStats:
    return DashboardStats(
        total_revenue=0,
        subscriptions=0,
        sales=0,
        active_users=1,
    )


@router.get(
    "/chart",
    operation_id="getDashboardChart",
    response_model=list[ChartDataPoint],
)
async def get_dashboard_chart(
    user: CurrentUser = Depends(get_current_user),
) -> list[ChartDataPoint]:
    return [
        ChartDataPoint(name="Jan", value=0),
        ChartDataPoint(name="Feb", value=0),
        ChartDataPoint(name="Mar", value=0),
        ChartDataPoint(name="Apr", value=0),
        ChartDataPoint(name="May", value=0),
        ChartDataPoint(name="Jun", value=0),
    ]
