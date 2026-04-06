import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneAccessCreate
from app.services.zone import ZoneService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

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
    name: str = Form(...),
    venue_id: uuid.UUID = Form(...),
    description: str | None = Form(None)
):
    zone_in = ZoneCreate(name=name, venue_id=venue_id, description=description)
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