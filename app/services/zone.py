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
        data = zone_in.model_dump()
        allowed_categories = data.pop("allowed_categories", [])
        
        zone = Zone(**data)
        self.session.add(zone)
        await self.session.flush()  # Generates the zone.id without committing
        
        # Instantly create the access rules selected in the form
        for cat_id in allowed_categories:
            self.session.add(ZoneAccess(zone_id=zone.id, category_id=cat_id))
            
        await self.session.commit()
        await self.session.refresh(zone)
        
        # Attach for the Pydantic response
        setattr(zone, "allowed_categories", allowed_categories)
        return zone

    async def get_zones(self) -> list[Zone]:
        stmt = select(Zone)
        result = await self.session.execute(stmt)
        zones = list(result.scalars().all())
        
        # Fetch all access rules at once to prevent N+1 query loops
        if zones:
            zone_ids = [z.id for z in zones]
            access_stmt = select(ZoneAccess.zone_id, ZoneAccess.category_id).where(ZoneAccess.zone_id.in_(zone_ids))
            access_result = await self.session.execute(access_stmt)
            
            access_map = {z.id: [] for z in zones}
            for zid, cid in access_result.all():
                access_map[zid].append(cid)
                
            for z in zones:
                setattr(z, "allowed_categories", access_map[z.id])
                
        return zones

    async def get_zone_by_id(self, zone_id: uuid.UUID) -> Zone:
        zone = await self.session.get(Zone, zone_id)
        if not zone:
            raise HTTPException(status_code=404, detail="Zone not found")
            
        access_stmt = select(ZoneAccess.category_id).where(ZoneAccess.zone_id == zone_id)
        cats = list((await self.session.execute(access_stmt)).scalars().all())
        setattr(zone, "allowed_categories", cats)
        return zone

    async def grant_access(self, zone_id: uuid.UUID, category_id: uuid.UUID) -> dict:
        # Check if this access rule already exists
        stmt = select(ZoneAccess).where(ZoneAccess.zone_id == zone_id, ZoneAccess.category_id == category_id)
        existing = await self.session.execute(stmt)
        if existing.scalars().first():
            return {"message": "Access already granted for this category."}
            
        self.session.add(ZoneAccess(zone_id=zone_id, category_id=category_id))
        await self.session.commit()
        
        # O(1) Cache Invalidation
        if self.redis:
            await self.redis.incr(f"zone_version:{zone_id}")
                
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