import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.participant import ParticipantRead, ParticipantListResponse
from app.services.participant import ParticipantService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

def get_participant_service(db: AsyncSession = Depends(get_db)) -> ParticipantService:
    return ParticipantService(db)

@router.get("/", response_model=ParticipantListResponse)
async def get_participants(
    current_user: Annotated[User, Depends(get_current_user)],
    service: ParticipantService = Depends(get_participant_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    tournament_id: uuid.UUID | None = Query(None, description="Filter by tournament ID"),
    role: str | None = Query(None, description="Filter by role")
):
    skip = (page - 1) * limit
    items, total = await service.get_participants(
        tournament_id=tournament_id,
        role=role,
        skip=skip, 
        limit=limit
    )
    return {"total": total, "items": items}

@router.get("/{participant_id}", response_model=ParticipantRead)
async def get_participant(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ParticipantService = Depends(get_participant_service)
):
    return await service.get_participant_by_id(participant_id)