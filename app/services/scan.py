import uuid
import json
import logging
import hmac
import hashlib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from redis.asyncio import Redis
from app.models.participant import Participant
from app.models.application import Application
from app.models.scan_log import ScanLog
from app.models.zone import Zone
from app.models.user import User
from app.models.zone_access import ZoneAccess
from app.models.organization import Organization
from app.models.badge import Badge
from app.config.settings import settings

logger = logging.getLogger(__name__)

class ScanService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.redis = redis

    def verify_qr_signature(self, participant_id: str, serial_number: str, signature: str, issued_at: int | None = None) -> bool:
        """Verifies the HMAC SHA-256 signature from the QR code."""
        if issued_at is not None:
            message = f"{participant_id}:{serial_number}:{issued_at}".encode("utf-8")
        else:
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

    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID, serial_number: str, signature: str, scanner_id: uuid.UUID, direction: str, issued_at: int | None = None) -> dict:
        # 0. Verify Cryptographic Signature (Zero-Trust Check)
        if not self.verify_qr_signature(str(participant_id), serial_number, signature, issued_at):
            logger.warning(f"FORGERY ATTEMPT: Invalid signature for participant {participant_id}")
            await self._log_scan(None, zone_id, scanner_id, False, "Invalid or forged QR code signature", direction)
            return {"access": "DENIED", "reason": "Invalid or forged QR code", "role": None}

        # 1. Authorization Check (O(1) Versioned Cache)
        z_version = await self.redis.get(f"zone_version:{zone_id}") or b"0"
        p_version = await self.redis.get(f"participant_version:{participant_id}") or b"0"
        if isinstance(z_version, bytes): z_version = z_version.decode("utf-8")
        if isinstance(p_version, bytes): p_version = p_version.decode("utf-8")

        auth_cache_key = f"auth:{participant_id}:v{p_version}:{zone_id}:v{z_version}"
        cached_auth = await self.redis.get(auth_cache_key)
        
        if cached_auth:
            auth_data = json.loads(cached_auth)
            is_granted = auth_data["is_granted"]
            reason = auth_data["reason"]
            role = auth_data["role"]
        else:
            # Cache Miss: Query DB
            zone = await self.session.get(Zone, zone_id)
            if not zone:
                await self._log_scan(participant_id, zone_id, scanner_id, False, "Zone does not exist", direction)
                return {"access": "DENIED", "reason": "Zone does not exist", "role": None}
                
            if not zone.is_active:
                is_granted = False
                reason = "Zone is currently closed."
                role = None
            else:
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
                
                # If the zone requires strict QR scan enforcement, check the access matrix
                if is_granted and zone.require_qr_scan:
                    access_stmt = select(ZoneAccess).where(ZoneAccess.zone_id == zone_id, ZoneAccess.category_id == participant.category_id)
                    if not (await self.session.execute(access_stmt)).scalars().first():
                        is_granted = False
                        reason = "Category does not have access to this zone."
                        
                role = participant.role
            await self.redis.set(auth_cache_key, json.dumps({"is_granted": is_granted, "reason": reason, "role": role}), ex=300)

        # 2. Anti-Passback (Atomic Check-and-Set via Lua)
        if is_granted:
            state_key = f"location:{participant_id}:{zone_id}"
            lua_script = """
            local current = redis.call('GET', KEYS[1])
            if current == ARGV[1] then
                return 0
            else
                redis.call('SETEX', KEYS[1], 43200, ARGV[1])
                return 1
            end
            """
            success = await self.redis.eval(lua_script, 1, state_key, direction)
            if not success:
                is_granted = False
                reason = f"Anti-passback violation: Participant is already marked as {direction}"
                role = None

        response = {
            "access": "GRANTED" if is_granted else "DENIED",
            "reason": reason,
            "role": role
        }
        
        await self._log_scan(participant_id, zone_id, scanner_id, is_granted, reason, direction)

        return response

    async def get_participant_profile(self, participant_id: uuid.UUID) -> dict | None:
        stmt = (
            select(
                Application.first_name,
                Application.last_name,
                Application.photo_url,
                Application.category,
                Application.emergency_contact_name,
                Application.emergency_contact_phone,
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
            "badge_status": row.badge_status,
            "emergency_contact_name": row.emergency_contact_name,
            "emergency_contact_phone": row.emergency_contact_phone
        }

    async def get_scan_logs(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        zone_id: uuid.UUID | None = None, 
        participant_id: uuid.UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        access_granted: bool | None = None
    ) -> tuple[list[dict], int]:
        count_stmt = select(func.count(ScanLog.id))
        
        stmt = (
            select(
                ScanLog, 
                Application.first_name, Application.last_name,
                Zone.name.label("zone_name"),
                User.first_name.label("scanner_first"), User.last_name.label("scanner_last")
            )
            .outerjoin(Participant, ScanLog.participant_id == Participant.id)
            .outerjoin(Application, Participant.application_id == Application.id)
            .join(Zone, ScanLog.zone_id == Zone.id)
            .join(User, ScanLog.scanner_id == User.id)
        )

        if zone_id:
            count_stmt = count_stmt.where(ScanLog.zone_id == zone_id)
            stmt = stmt.where(ScanLog.zone_id == zone_id)
        if participant_id:
            count_stmt = count_stmt.where(ScanLog.participant_id == participant_id)
            stmt = stmt.where(ScanLog.participant_id == participant_id)
        if start_date:
            count_stmt = count_stmt.where(ScanLog.created_at >= start_date)
            stmt = stmt.where(ScanLog.created_at >= start_date)
        if end_date:
            count_stmt = count_stmt.where(ScanLog.created_at <= end_date)
            stmt = stmt.where(ScanLog.created_at <= end_date)
        if access_granted is not None:
            count_stmt = count_stmt.where(ScanLog.access_granted == access_granted)
            stmt = stmt.where(ScanLog.access_granted == access_granted)

        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(ScanLog.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)

        logs = []
        for scan_log, p_first, p_last, z_name, s_first, s_last in result.all():
            log_dict = {c.name: getattr(scan_log, c.name) for c in scan_log.__table__.columns}
            log_dict["participant_name"] = f"{p_first} {p_last}" if p_first and p_last else "Unknown / Forged"
            log_dict["zone_name"] = z_name
            log_dict["scanner_name"] = f"{s_first} {s_last}"
            logs.append(log_dict)
            
        return logs, total