import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from redis.asyncio import Redis
from app.models.zone import Zone
from app.models.zone_access import ZoneAccess
from app.models.scan_log import ScanLog
from app.schemas.zone import ZoneCreate

class ZoneService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None):
        self.session = session
        self.redis = redis

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
        
        # Invalidate scanner cache for this zone so newly allowed participants can enter immediately
        if self.redis:
            cache_pattern = f"auth:*:{zone_id}"
            keys = await self.redis.keys(cache_pattern)
            if keys:
                await self.redis.delete(*keys)
                
        return {"message": "Access granted successfully."}

    async def get_zone_capacity(self, zone_id: uuid.UUID) -> dict:
        # Count all GRANTED 'IN' scans vs GRANTED 'OUT' scans for this zone
        in_stmt = select(func.count(ScanLog.id)).where(
            ScanLog.zone_id == zone_id, ScanLog.access_granted == True, ScanLog.direction == "IN"
        )
        out_stmt = select(func.count(ScanLog.id)).where(
            ScanLog.zone_id == zone_id, ScanLog.access_granted == True, ScanLog.direction == "OUT"
        )
        
        ins = (await self.session.execute(in_stmt)).scalar() or 0
        outs = (await self.session.execute(out_stmt)).scalar() or 0
        
        current_capacity = max(0, ins - outs)
        return {"zone_id": zone_id, "current_capacity": current_capacity, "total_entries": ins, "total_exits": outs}