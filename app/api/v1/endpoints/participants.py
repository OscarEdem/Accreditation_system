import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.participant import ParticipantCreate, ParticipantRead
from app.services.participant import ParticipantService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

def get_participant_service(db: AsyncSession = Depends(get_db)) -> ParticipantService:
    return ParticipantService(db)

@router.post("/", response_model=ParticipantRead, status_code=201)
async def create_participant(
    participant_in: ParticipantCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ParticipantService = Depends(get_participant_service)
):
    return await service.create_participant(participant_in)

@router.get("/", response_model=List[ParticipantRead])
async def get_participants(
    current_user: Annotated[User, Depends(get_current_user)],
    service: ParticipantService = Depends(get_participant_service)
):
    return await service.get_participants()

@router.get("/{participant_id}", response_model=ParticipantRead)
async def get_participant(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ParticipantService = Depends(get_participant_service)
):
    return await service.get_participant_by_id(participant_id)