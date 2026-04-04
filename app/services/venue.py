import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.venue import Venue
from app.schemas.venue import VenueCreate

class VenueService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_venue(self, venue_in: VenueCreate) -> Venue:
        venue = Venue(**venue_in.model_dump())
        self.session.add(venue)
        await self.session.commit()
        await self.session.refresh(venue)
        return venue

    async def get_venues(self) -> list[Venue]:
        stmt = select(Venue)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_venue_by_id(self, venue_id: uuid.UUID) -> Venue:
        venue = await self.session.get(Venue, venue_id)
        if not venue:
            raise HTTPException(status_code=404, detail="Venue not found")
        return venue