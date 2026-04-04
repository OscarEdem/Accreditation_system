import uuid
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from app.models.participant import Participant
from app.models.application import Application

logger = logging.getLogger(__name__)

class ScanService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis

    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID) -> dict:
        cache_key = f"scan:{participant_id}:{zone_id}"
        
        # 1. Check Redis Cache (Strict dependency)
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # 2. Cache Miss: Query DB (Join Participant and Linked Application)
        stmt = (
            select(Participant, Application.status)
            .join(Application, Participant.application_id == Application.id)
            .where(Participant.id == participant_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row:
            return {"access": "DENIED", "reason": "Participant not found", "role": None}
        
        participant, application_status = row
        
        # 3. Determine Access
        # TODO: Implement Access Matrix validation here to check if participant.role / application.category
        # has permission for the specific zone_id requested.
        
        is_granted = application_status.lower() == "approved"
        response = {
            "access": "GRANTED" if is_granted else "DENIED",
            "reason": None if is_granted else f"Application status: {application_status}",
            "role": participant.role
        }
        
        # 4. Set Cache for future scans (e.g., expire in 5 minutes)
        await self.redis.set(cache_key, json.dumps(response), ex=300)
        
        return response