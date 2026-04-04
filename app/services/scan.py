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
from app.models.scan_log import ScanLog
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

    async def _log_scan(self, participant_id: uuid.UUID | None, zone_id: uuid.UUID, scanner_id: uuid.UUID, access_granted: bool, reason: str | None):
        """Logs the scan event to the database for auditing."""
        log_entry = ScanLog(
            participant_id=participant_id,
            zone_id=zone_id,
            scanner_id=scanner_id,
            access_granted=access_granted,
            reason=reason
        )
        self.session.add(log_entry)
        await self.session.commit()

    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID, serial_number: str, signature: str, scanner_id: uuid.UUID) -> dict:
        # 0. Verify Cryptographic Signature (Zero-Trust Check)
        if not self.verify_qr_signature(str(participant_id), serial_number, signature):
            logger.warning(f"FORGERY ATTEMPT: Invalid signature for participant {participant_id}")
            await self._log_scan(None, zone_id, scanner_id, False, "Invalid or forged QR code signature")
            return {"access": "DENIED", "reason": "Invalid or forged QR code", "role": None}

        cache_key = f"scan:{participant_id}:{zone_id}"
        
        # 1. Check Redis Cache (Strict dependency)
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            response = json.loads(cached_data)
            await self._log_scan(participant_id, zone_id, scanner_id, response["access"] == "GRANTED", response.get("reason"))
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
            await self._log_scan(None, zone_id, scanner_id, False, "Participant not found")
            return {"access": "DENIED", "reason": "Participant not found", "role": None}
        
        participant, application_status = row
        
        # 3. Determine Access
        # Basic Status Check
        is_granted = application_status.lower() == "approved"
        reason = None if is_granted else f"Application status: {application_status}"
        
        # Access Matrix Check (Placeholder logic for future Phase 2 expansion)
        if is_granted:
            # Example: if zone.name == "VIP" and participant.role != "vip": is_granted = False
            # This is where you would query a dedicated ZoneAccess table linking roles to zones.
            pass

        response = {
            "access": "GRANTED" if is_granted else "DENIED",
            "reason": None if is_granted else f"Application status: {application_status}",
            "role": participant.role
        }
        
        # 4. Set Cache for future scans (e.g., expire in 5 minutes)
        await self.redis.set(cache_key, json.dumps(response), ex=300)
        
        # Log the result
        await self._log_scan(participant_id, zone_id, scanner_id, is_granted, reason)

        return response