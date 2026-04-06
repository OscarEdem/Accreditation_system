import uuid
import json
import logging
import hmac
import hashlib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from app.models.participant import Participant
from app.models.application import Application
from app.models.scan_log import ScanLog
from app.models.zone_access import ZoneAccess
from app.models.organization import Organization
from app.models.badge import Badge
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

    async def _log_scan(self, participant_id: uuid.UUID | None, zone_id: uuid.UUID, scanner_id: uuid.UUID, access_granted: bool, reason: str | None, direction: str):
        """Logs the scan event to the database for auditing."""
        log_entry = ScanLog(
            participant_id=participant_id,
            zone_id=zone_id,
            scanner_id=scanner_id,
            access_granted=access_granted,
            reason=reason,
            direction=direction
        )
        self.session.add(log_entry)
        await self.session.commit()

        # Push a live notification to Redis Pub/Sub if access is DENIED
        if not access_granted and self.redis:
            alert = {
                "event": "SCAN_DENIED",
                "participant_id": str(participant_id) if participant_id else None,
                "zone_id": str(zone_id),
                "scanner_id": str(scanner_id),
                "direction": direction,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.redis.publish("scan_alerts", json.dumps(alert))

    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID, serial_number: str, signature: str, scanner_id: uuid.UUID, direction: str) -> dict:
        # 0. Verify Cryptographic Signature (Zero-Trust Check)
        if not self.verify_qr_signature(str(participant_id), serial_number, signature):
            logger.warning(f"FORGERY ATTEMPT: Invalid signature for participant {participant_id}")
            await self._log_scan(None, zone_id, scanner_id, False, "Invalid or forged QR code signature", direction)
            return {"access": "DENIED", "reason": "Invalid or forged QR code", "role": None}

        # 1. Anti-Passback Check (Are they already IN or OUT?)
        state_key = f"location:{participant_id}:{zone_id}"
        last_direction = await self.redis.get(state_key)
        
        if last_direction and isinstance(last_direction, bytes):
            last_direction = last_direction.decode("utf-8")
            
        if not last_direction:
            # Cache miss for state: check DB for last successful scan
            last_scan_stmt = (
                select(ScanLog.direction)
                .where(ScanLog.participant_id == participant_id, ScanLog.zone_id == zone_id, ScanLog.access_granted == True)
                .order_by(ScanLog.created_at.desc())
                .limit(1)
            )
            last_direction = (await self.session.execute(last_scan_stmt)).scalar()
            
        if last_direction == direction:
            reason = f"Anti-passback violation: Participant is already marked as {direction}"
            await self._log_scan(participant_id, zone_id, scanner_id, False, reason, direction)
            return {"access": "DENIED", "reason": reason, "role": None}

        # 2. Authorization Check (Use Cache)
        auth_cache_key = f"auth:{participant_id}:{zone_id}"
        cached_auth = await self.redis.get(auth_cache_key)
        
        if cached_auth:
            auth_data = json.loads(cached_auth)
            is_granted = auth_data["is_granted"]
            reason = auth_data["reason"]
            role = auth_data["role"]
        else:
            # Cache Miss: Query DB
            stmt = (
                select(Participant, Application.status)
                .join(Application, Participant.application_id == Application.id)
                .where(Participant.id == participant_id)
            )
            row = (await self.session.execute(stmt)).first()
            
            if not row:
                await self._log_scan(None, zone_id, scanner_id, False, "Participant not found", direction)
                return {"access": "DENIED", "reason": "Participant not found", "role": None}
                
            participant, application_status = row
            is_granted = application_status.lower() == "approved"
            reason = None if is_granted else f"Application status: {application_status}"
            
            if is_granted:
                access_stmt = select(ZoneAccess).where(ZoneAccess.zone_id == zone_id, ZoneAccess.category_id == participant.category_id)
                if not (await self.session.execute(access_stmt)).scalars().first():
                    is_granted = False
                    reason = "Category does not have access to this zone."
                    
            role = participant.role
            await self.redis.set(auth_cache_key, json.dumps({"is_granted": is_granted, "reason": reason, "role": role}), ex=300)

        response = {
            "access": "GRANTED" if is_granted else "DENIED",
            "reason": reason,
            "role": role
        }
        
        # 3. Finalize & Log
        if is_granted:
            # Update physical location state (expires in 12 hours to auto-reset next day)
            await self.redis.set(state_key, direction, ex=43200)
        
        await self._log_scan(participant_id, zone_id, scanner_id, is_granted, reason, direction)

        return response

    async def get_participant_profile(self, participant_id: uuid.UUID) -> dict | None:
        stmt = (
            select(
                Application.first_name,
                Application.last_name,
                Application.photo_url,
                Application.category,
                Participant.role,
                Organization.name.label("organization_name"),
                Badge.status.label("badge_status")
            )
            .select_from(Participant)
            .join(Application, Participant.application_id == Application.id)
            .outerjoin(Organization, Application.organization_id == Organization.id)
            .outerjoin(Badge, Badge.participant_id == Participant.id)
            .where(Participant.id == participant_id)
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row:
            return None
            
        return {
            "first_name": row.first_name,
            "last_name": row.last_name,
            "photo_url": row.photo_url,
            "category": row.category,
            "role": row.role,
            "organization_name": row.organization_name,
            "badge_status": row.badge_status
        }