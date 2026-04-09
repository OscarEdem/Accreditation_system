import uuid
from typing import List, Annotated
from datetime import date
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.schemas.tournament import TournamentCreate, TournamentRead
from app.services.tournament import TournamentService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.venue import Venue
from app.models.tournament import Tournament

router = APIRouter()

allow_admin = RoleChecker(["admin"])

def get_tournament_service(db: AsyncSession = Depends(get_db)) -> TournamentService:
    return TournamentService(db)

@router.post("/", response_model=TournamentRead, status_code=201)
async def create_tournament(
    current_user: Annotated[User, Depends(allow_admin)],
    service: TournamentService = Depends(get_tournament_service),
    name: str = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    host_city: str = Form(...),
    venue_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    description: str | None = Form(None)
):
    if not venue_id:
        default_venue = await db.scalar(select(Venue).order_by(Venue.created_at.asc()).limit(1))
        if not default_venue:
            raise HTTPException(status_code=400, detail="No venues exist in the system to auto-assign.")
        venue_id = default_venue.id
        
    tournament_in = TournamentCreate(name=name, start_date=start_date, end_date=end_date, host_city=host_city, venue_id=venue_id, description=description)
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

@router.patch("/{tournament_id}/toggle-active", response_model=TournamentRead, summary="Toggle Tournament Status")
async def toggle_tournament_active(
    tournament_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db)
):
    """Turn a tournament ON or OFF for accepting new applications."""
    tournament = await db.get(Tournament, tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    tournament.is_active = not tournament.is_active
    await db.commit()
    await db.refresh(tournament)
    return tournament