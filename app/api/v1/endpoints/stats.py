from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.stats import DashboardStats
from app.services.stats import StatsService
from app.api.deps import RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_stats_service(db: AsyncSession = Depends(get_db)) -> StatsService:
    return StatsService(db)

@router.get("/", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: Annotated[User, Depends(allow_admin)],
    service: StatsService = Depends(get_stats_service)
):
    return await service.get_dashboard_stats()