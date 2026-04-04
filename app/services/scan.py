import uuid
import json
import logging
import hmac
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from app.models.participant import Participant
from app.models.application import Application
from app.config.settings import settings

logger = logging.getLogger(__name__)

class ScanService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis

    def verify_qr_signature(self, participant_id: str, serial_number: str, signature: str) -> bool:
        """Verifies the HMAC SHA-256 signature from the QR code."""
        message = f"{participant_id}:{serial_number}".encode("utf-8")
        secret = settings.SECRET_KEY.encode("utf-8")
        expected_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID, serial_number: str, signature: str) -> dict:
        # 0. Verify Cryptographic Signature (Zero-Trust Check)
        if not self.verify_qr_signature(str(participant_id), serial_number, signature):
            logger.warning(f"FORGERY ATTEMPT: Invalid signature for participant {participant_id}")
            return {"access": "DENIED", "reason": "Invalid or forged QR code", "role": None}

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