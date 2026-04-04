import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.participant import Participant
from app.schemas.participant import ParticipantCreate

class ParticipantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_participant(self, participant_in: ParticipantCreate) -> Participant:
        participant = Participant(**participant_in.model_dump())
        self.session.add(participant)
        await self.session.commit()
        await self.session.refresh(participant)
        return participant

    async def create_participants_batch(self, participants_in: list[ParticipantCreate]) -> list[Participant]:
        participants = [Participant(**p.model_dump()) for p in participants_in]
        self.session.add_all(participants)
        await self.session.commit()
        for p in participants:
            await self.session.refresh(p)
        return participants

    async def get_participants(
        self, 
        tournament_id: uuid.UUID | None = None,
        role: str | None = None,
        skip: int = 0, 
        limit: int = 100
    ) -> tuple[list[Participant], int]:
        count_stmt = select(func.count(Participant.id))
        stmt = select(Participant)
        
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
        participant = await self.session.get(Participant, participant_id)
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
        return participant