import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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

    async def get_participants(self) -> list[Participant]:
        stmt = select(Participant)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_participant_by_id(self, participant_id: uuid.UUID) -> Participant:
        participant = await self.session.get(Participant, participant_id)
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
        return participant