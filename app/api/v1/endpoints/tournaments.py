import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.tournament import TournamentCreate, TournamentRead
from app.services.tournament import TournamentService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin"])

def get_tournament_service(db: AsyncSession = Depends(get_db)) -> TournamentService:
    return TournamentService(db)

@router.post("/", response_model=TournamentRead, status_code=201)
async def create_tournament(
    tournament_in: TournamentCreate,
    current_user: Annotated[User, Depends(allow_admin)],
    service: TournamentService = Depends(get_tournament_service)
):
    return await service.create_tournament(tournament_in)

@router.get("/", response_model=List[TournamentRead])
async def get_tournaments(
    current_user: Annotated[User, Depends(get_current_user)],
    service: TournamentService = Depends(get_tournament_service)
):
    return await service.get_tournaments()

@router.get("/{tournament_id}", response_model=TournamentRead)
async def get_tournament(
    tournament_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: TournamentService = Depends(get_tournament_service)
):
    return await service.get_tournament_by_id(tournament_id)