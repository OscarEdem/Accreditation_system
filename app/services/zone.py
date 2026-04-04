import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.zone import Zone
from app.models.zone_access import ZoneAccess
from app.schemas.zone import ZoneCreate

class ZoneService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_zone(self, zone_in: ZoneCreate) -> Zone:
        zone = Zone(**zone_in.model_dump())
        self.session.add(zone)
        await self.session.commit()
        await self.session.refresh(zone)
        return zone

    async def get_zones(self) -> list[Zone]:
        stmt = select(Zone)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_zone_by_id(self, zone_id: uuid.UUID) -> Zone:
        zone = await self.session.get(Zone, zone_id)
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
        return zone

    async def grant_access(self, zone_id: uuid.UUID, category_id: uuid.UUID) -> dict:
        # Check if this access rule already exists
        stmt = select(ZoneAccess).where(ZoneAccess.zone_id == zone_id, ZoneAccess.category_id == category_id)
        existing = await self.session.execute(stmt)
        if existing.scalars().first():
            return {"message": "Access already granted for this category."}
            
        self.session.add(ZoneAccess(zone_id=zone_id, category_id=category_id))
        await self.session.commit()
        return {"message": "Access granted successfully."}