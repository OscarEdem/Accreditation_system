import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.participant import Participant
from app.schemas.participant import ParticipantCreate, ParticipantRole
from app.models.application import Application

class ParticipantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _derive_role_from_application(self, application_id: uuid.UUID) -> ParticipantRole:
        application = await self.session.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        category = application.category.lower()
        if "athlete" in category or category == "a":
            return ParticipantRole.athlete
        elif "media" in category or category == "m":
            return ParticipantRole.media
        elif "vip" in category or category == "v":
            return ParticipantRole.vip
        elif "medical" in category:
            return ParticipantRole.medical
        elif "security" in category:
            return ParticipantRole.security
        elif "official" in category:
            return ParticipantRole.team_official
        return ParticipantRole.staff  # Default fallback

    async def create_participant(self, participant_in: ParticipantCreate) -> Participant:
        role = participant_in.role or await self._derive_role_from_application(participant_in.application_id)
        
        participant_data = participant_in.model_dump(exclude_unset=True)
        participant_data["role"] = role
        
        participant = Participant(**participant_data)
        self.session.add(participant)
        try:
            await self.session.commit()
            await self.session.refresh(participant)
            return participant
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="Invalid application_id or tournament_id. Please ensure they exist.")

    async def create_participants_batch(self, participants_in: list[ParticipantCreate]) -> list[Participant]:
        participants = []
        for p_in in participants_in:
            role = p_in.role or await self._derive_role_from_application(p_in.application_id)
            p_data = p_in.model_dump(exclude_unset=True)
            p_data["role"] = role
            participants.append(Participant(**p_data))
            
        self.session.add_all(participants)
        try:
            await self.session.commit()
            for p in participants:
                await self.session.refresh(p)
            return participants
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="One or more invalid application_ids or tournament_ids.")

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