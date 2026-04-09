import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.participant import Participant
from app.models.application import Application

class ParticipantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_participants(
        self, 
        tournament_id: uuid.UUID | None = None,
        role: str | None = None,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[list[Participant], int]:
        count_stmt = select(func.count(Participant.id))
        stmt = select(Participant)
        
        if user_id:
            count_stmt = count_stmt.join(Application, Participant.application_id == Application.id).where(Application.user_id == user_id)
            stmt = stmt.join(Application, Participant.application_id == Application.id).where(Application.user_id == user_id)
        if organization_id:
            count_stmt = count_stmt.where(Participant.organization_id == organization_id)
            stmt = stmt.where(Participant.organization_id == organization_id)
        if tournament_id:
            count_stmt = count_stmt.where(Participant.tournament_id == tournament_id)
            stmt = stmt.where(Participant.tournament_id == tournament_id)
        if role:
            count_stmt = count_stmt.where(Participant.role == role)
            stmt = stmt.where(Participant.role == role)
            
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_participant_by_id(self, participant_id: uuid.UUID) -> Participant:
        stmt = select(Participant).where(
            (Participant.id == participant_id) | (Participant.application_id == participant_id)
        )
        participant = (await self.session.execute(stmt)).scalars().first()
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
        return participant