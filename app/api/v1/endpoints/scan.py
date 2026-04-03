import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.schemas.scan import ScanRequest, ScanResponse
from app.services.scan import ScanService

router = APIRouter()
logger = logging.getLogger(__name__)

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
    service: ScanService = Depends(get_scan_service),
    redis: Redis = Depends(get_redis)
):
    # Rate Limiting: Max 10 scans per 10 seconds per scanner device
    rate_limit_key = f"rate_limit:scan:user:{current_user.id}"
    
    try:
        requests_made = await redis.incr(rate_limit_key)
        if requests_made == 1:
            await redis.expire(rate_limit_key, 10)  # 10-second window
            
        if requests_made > 10:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many scans. Please slow down.")
    except HTTPException:
        raise  # Re-raise the 429 if the limit is actually hit
    except Exception as e:
        logger.warning(f"Redis rate limiting failed for user {current_user.id}: {e}")

    return await service.process_scan(request.participant_id, request.zone_id)