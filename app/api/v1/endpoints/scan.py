from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.schemas.scan import ScanRequest, ScanResponse
from app.services.scan import ScanService

router = APIRouter()

allow_scan_roles = RoleChecker(["admin", "scanner"])

def get_scan_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> ScanService:
    return ScanService(db, redis)

@router.post("/", response_model=ScanResponse, status_code=200)
async def scan_participant(
    request: ScanRequest,
    current_user: Annotated[User, Depends(allow_scan_roles)],
    service: ScanService = Depends(get_scan_service)
):
    return await service.process_scan(request.participant_id, request.zone_id)