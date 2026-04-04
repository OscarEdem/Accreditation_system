import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.venue import VenueCreate, VenueRead
from app.services.venue import VenueService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin"])

def get_venue_service(db: AsyncSession = Depends(get_db)) -> VenueService:
    return VenueService(db)

@router.post("/", response_model=VenueRead, status_code=201)
async def create_venue(
    venue_in: VenueCreate,
    current_user: Annotated[User, Depends(allow_admin)],
    service: VenueService = Depends(get_venue_service)
):
    return await service.create_venue(venue_in)

@router.get("/", response_model=List[VenueRead])
async def get_venues(
    current_user: Annotated[User, Depends(get_current_user)],
    service: VenueService = Depends(get_venue_service)
):
    return await service.get_venues()

@router.get("/{venue_id}", response_model=VenueRead)
async def get_venue(
    venue_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: VenueService = Depends(get_venue_service)
):
    return await service.get_venue_by_id(venue_id)