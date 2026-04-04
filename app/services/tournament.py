import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.tournament import Tournament
from app.schemas.tournament import TournamentCreate

class TournamentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tournament(self, tournament_in: TournamentCreate) -> Tournament:
        tournament = Tournament(**tournament_in.model_dump())
        self.session.add(tournament)
        await self.session.commit()
        await self.session.refresh(tournament)
        return tournament

    async def get_tournaments(self) -> list[Tournament]:
        stmt = select(Tournament)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_tournament_by_id(self, tournament_id: uuid.UUID) -> Tournament:
        tournament = await self.session.get(Tournament, tournament_id)
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        return tournament