import logging
import uuid
import asyncio
import jwt
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.schemas.scan import ScanRequest, ScanResponse, ScanParticipantProfile, ScanLogListResponse
from app.services.scan import ScanService
from app.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

allow_scan_roles = RoleChecker(["admin", "scanner"])

def get_scan_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> ScanService:
    return ScanService(db, redis)

@router.post("/", response_model=ScanResponse, status_code=200, summary="Process Physical QR Scan")
async def scan_participant(
    request: ScanRequest,
    current_user: Annotated[User, Depends(allow_scan_roles)],
    service: ScanService = Depends(get_scan_service),
    redis: Redis = Depends(get_redis)
):
    """
    The core endpoint hit by physical mobile scanners at the venue gates.
    
    **Security Features Executed Instantly:**
    - Rate-limits to prevent API spam (max 10 scans per 10s per device).
    - Re-hashes the QR signature locally to detect cryptographic forgery.
    - Checks Anti-passback rules.
    - Checks if the participant's category has access to the requested `zone_id`.
    - Logs the interaction to `ScanLog` permanently.
    """
    # Rate Limiting: Max 10 scans per 10 seconds per scanner device
    rate_limit_key = f"rate_limit:scan:user:{current_user.id}"
    
    requests_made = await redis.incr(rate_limit_key)
    if requests_made == 1:
        await redis.expire(rate_limit_key, 10)  # 10-second window
        
    if requests_made > 10:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many scans. Please slow down.")

    return await service.process_scan(
        participant_id=request.participant_id,
        zone_id=request.zone_id,
        serial_number=request.serial_number,
        signature=request.signature,
        scanner_id=current_user.id,
        direction=request.direction
    )

@router.get("/participant/{participant_id}", response_model=ScanParticipantProfile, status_code=200, summary="Get Scanned Profile Details")
async def get_participant_profile(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_scan_roles)],
    service: ScanService = Depends(get_scan_service)
):
    """
    Used by the physical scanner app. If a scan is successful, the app calls this endpoint 
    to download the participant's photo and name to display on the guard's screen to verify identity.
    """
    profile = await service.get_participant_profile(participant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Participant not found")
    return profile

@router.get("/logs", response_model=ScanLogListResponse, status_code=200, summary="List Scan Logs (Paginated)")
async def get_scan_logs(
    current_user: Annotated[User, Depends(allow_scan_roles)],
    service: ScanService = Depends(get_scan_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    zone_id: uuid.UUID | None = Query(None, description="Filter by zone ID"),
    participant_id: uuid.UUID | None = Query(None, description="Filter by participant ID"),
    start_date: datetime | None = Query(None, description="Filter from this start date (ISO 8601)"),
    end_date: datetime | None = Query(None, description="Filter up to this end date (ISO 8601)"),
    access_granted: bool | None = Query(None, description="Filter by access granted status (true/false)")
):
    """
    Retrieves a historical list of all physical gate interactions. 
    Used for the security audit dashboard to trace exactly when and where a person entered a zone.
    """
    skip = (page - 1) * limit
    items, total = await service.get_scan_logs(
        skip=skip, 
        limit=limit, 
        zone_id=zone_id, 
        participant_id=participant_id,
        start_date=start_date,
        end_date=end_date,
        access_granted=access_granted
    )
    return {"total": total, "items": items}

@router.websocket("/live-alerts", name="Connect to WebSocket")
async def scan_live_alerts(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    WebSocket endpoint to push live 'DENIED' scan alerts to the admin dashboard.
    
    **Frontend Implementation Notes:**
    - Connect via `wss://<domain>/api/v1/scan/live-alerts?token=<your_jwt_token>`
    - The backend will push a JSON string whenever a malicious or unauthorized scan occurs at any gate.
    """
    # 1. Authenticate the WebSocket connection using the query parameter token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not email:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            return
    except jwt.InvalidTokenError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return
        
    # 2. Authorize the user based on role
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or user.role not in ["admin", "loc_admin", "scanner"]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized role")
        return

    await websocket.accept()
    
    # Subscribe to the Redis Pub/Sub channel
    pubsub = redis.pubsub()
    await pubsub.subscribe("scan_alerts")
    
    async def redis_listener():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception as e:
            logger.error(f"WebSocket Redis Listener Error: {e}")
            
    # Run the Redis listener in the background
    listener_task = asyncio.create_task(redis_listener())
    
    try:
        while True:
            # Keep connection alive and detect if the client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        listener_task.cancel()
        await pubsub.unsubscribe("scan_alerts")
        await pubsub.close()