import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneUpdate, ZoneAccessCreate, ZoneMatrixItem, ZoneAccessToggleResponse
from app.services.zone import ZoneService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.zone import Zone
from app.models.zone_access import ZoneAccess
from app.models.venue import Venue
from app.models.audit_log import AuditLog

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_zone_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> ZoneService:
    return ZoneService(db, redis)

@router.post("/", response_model=ZoneRead, status_code=201)
async def create_zone(
    current_user: Annotated[User, Depends(allow_admin)],
    service: ZoneService = Depends(get_zone_service),
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    venue_id: uuid.UUID | None = Form(None),
    description: str | None = Form(None),
    code: str | None = Form(None),
    color: str | None = Form("#3B82F6"),
    is_active: bool = Form(True),
    require_qr_scan: bool = Form(True),
    allowed_categories: list[uuid.UUID] = Form(default=[])
):
    """Admin endpoint to create a new access zone with rules and styling."""
    if not venue_id:
        default_venue = await db.scalar(select(Venue).order_by(Venue.created_at.asc()).limit(1))
        if not default_venue:
            raise HTTPException(status_code=400, detail="No venues exist in the system to auto-assign.")
        venue_id = default_venue.id
        
    zone_in = ZoneCreate(
        name=name, 
        venue_id=venue_id, 
        description=description,
        code=code,
        color=color,
        is_active=is_active,
        require_qr_scan=require_qr_scan,
        allowed_categories=allowed_categories
    )
    return await service.create_zone(zone_in)

@router.get("/", response_model=List[ZoneRead])
async def get_zones(
    current_user: Annotated[User, Depends(get_current_user)],
    service: ZoneService = Depends(get_zone_service)
):
    return await service.get_zones()

@router.get("/{zone_id}", response_model=ZoneRead)
async def get_zone(
    zone_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ZoneService = Depends(get_zone_service)
):
    return await service.get_zone_by_id(zone_id)

@router.patch("/{zone_id}", response_model=ZoneRead, summary="Update Zone")
async def update_zone(
    zone_id: uuid.UUID,
    update_in: ZoneUpdate,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Updates a zone's details, including its access rules and styling."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
        
    update_data = update_in.model_dump(exclude_unset=True)
    allowed_categories = update_data.pop("allowed_categories", None)
    
    needs_cache_clear = False
    if "is_active" in update_data and update_data["is_active"] != zone.is_active:
        needs_cache_clear = True
        
    for field, value in update_data.items():
        setattr(zone, field, value)
        
    if allowed_categories is not None:
        # Safely wipe old rules and insert the updated ones
        await db.execute(delete(ZoneAccess).where(ZoneAccess.zone_id == zone_id))
        if allowed_categories:
            new_access = [ZoneAccess(zone_id=zone_id, category_id=cat_id) for cat_id in allowed_categories]
            db.add_all(new_access)
        needs_cache_clear = True
        
    # Security Audit Trail
    audit = AuditLog(
        entity_type="zone",
        entity_id=zone_id,
        action="zone_updated",
        user_id=current_user.id
    )
    db.add(audit)

    await db.commit()
    await db.refresh(zone)
    
    # 🔒 ZERO-TRUST: O(1) Cache Invalidation via Version Bumping
    if needs_cache_clear:
        await redis.incr(f"zone_version:{zone_id}")
        
    # Manually fetch and attach allowed_categories for the response
    access_stmt = select(ZoneAccess.category_id).where(ZoneAccess.zone_id == zone_id)
    cats = list((await db.execute(access_stmt)).scalars().all())
    setattr(zone, "allowed_categories", cats)
            
    return zone

@router.patch("/{zone_id}/toggle-active", response_model=ZoneRead, summary="Toggle Zone Status")
async def toggle_zone_active(
    zone_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Turn a zone ON or OFF. If turned OFF, it instantly revokes all cached access."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone.is_active = not zone.is_active
    await db.commit()
    await db.refresh(zone)
    
    # 🔒 ZERO-TRUST: O(1) Cache Invalidation
    if not zone.is_active:
        await redis.incr(f"zone_version:{zone_id}")
        
    # Manually fetch and attach allowed_categories for the response
    access_stmt = select(ZoneAccess.category_id).where(ZoneAccess.zone_id == zone_id)
    cats = list((await db.execute(access_stmt)).scalars().all())
    setattr(zone, "allowed_categories", cats)
            
    return zone

@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Zone")
async def delete_zone(
    zone_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Permanently deletes a zone and its associated access rules."""
    zone = await db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
        
    await db.execute(delete(ZoneAccess).where(ZoneAccess.zone_id == zone_id))
    await db.delete(zone)
    await db.commit()
    
    # 🔒 ZERO-TRUST: O(1) Cache Invalidation
    await redis.incr(f"zone_version:{zone_id}")

@router.post("/{zone_id}/access", status_code=201)
async def grant_zone_access(
    zone_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: ZoneService = Depends(get_zone_service),
    category_id: uuid.UUID = Form(...)
):
    return await service.grant_access(zone_id, category_id)

@router.get("/{zone_id}/capacity", status_code=200)
async def get_zone_capacity(
    zone_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ZoneService = Depends(get_zone_service)
):
    return await service.get_zone_capacity(zone_id)

@router.get("/venue/{venue_id}/access-matrix", response_model=list[ZoneMatrixItem], summary="Get Venue Access Matrix")
async def get_venue_access_matrix(
    venue_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches all active access rules for a specific venue.
    
    **Frontend Implementation Notes:**
    - Call this endpoint ONCE when the Access Matrix page loads.
    - It returns an array of objects mapping `zone_id` to `category_id`.
    - **Usage:** Loop through these pairs to pre-check the specific cells in your frontend data grid!
    """
    stmt = (
        select(ZoneAccess)
        .join(Zone, ZoneAccess.zone_id == Zone.id)
        .where(Zone.venue_id == venue_id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{zone_id}/access/toggle", response_model=ZoneAccessToggleResponse, summary="Toggle Matrix Checkbox")
async def toggle_zone_access(
    zone_id: uuid.UUID,
    request: ZoneAccessCreate,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Toggles access for a category to a specific zone in real-time.
    
    **Frontend Implementation Notes:**
    - Call this endpoint EVERY TIME an admin clicks a checkbox cell in the Access Matrix.
    - If the category already has access, this will **revoke** it. 
    - If the category does not have access, this will **grant** it.
    - The backend handles cache invalidation and Audit Logging automatically.
    
    **Example Body:**
    ```json
    {
      "category_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    ```
    """
    stmt = select(ZoneAccess).where(
        ZoneAccess.zone_id == zone_id,
        ZoneAccess.category_id == request.category_id
    )
    access = (await db.execute(stmt)).scalars().first()
    
    if access:
        await db.delete(access)
        granted = False
        message = "Access revoked."
        action_type = "revoke_zone_access"
    else:
        new_access = ZoneAccess(zone_id=zone_id, category_id=request.category_id)
        db.add(new_access)
        granted = True
        message = "Access granted."
        action_type = "grant_zone_access"
        
    # Security Audit Trail
    audit = AuditLog(
        entity_type="zone_access",
        entity_id=zone_id,
        action=action_type,
        new_value=f"Category ID: {request.category_id}",
        user_id=current_user.id
    )
    db.add(audit)
        
    await db.commit()
    
    # 🔒 ZERO-TRUST SECURITY: O(1) Cache Invalidation
    await redis.incr(f"zone_version:{zone_id}")
        
    return {
        "granted": granted, 
        "message": message, 
        "zone_id": zone_id, 
        "category_id": request.category_id
    }