import hmac
import hashlib
import json
import uuid
import base64
import qrcode
from io import BytesIO
from datetime import timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from redis.asyncio import Redis
from app.config.settings import settings
from app.models.badge import Badge

class BadgeService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None):
        self.session = session
        self.redis = redis

    def generate_signature(self, participant_id: str, serial_number: str, issued_at: int | None = None) -> str:
        """Generates an HMAC SHA-256 signature for the badge data."""
        if issued_at is not None:
            message = f"{participant_id}:{serial_number}:{issued_at}".encode("utf-8")
        else:
            message = f"{participant_id}:{serial_number}".encode("utf-8")
        secret = settings.SECRET_KEY.encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    async def create_badge(self, participant_id: uuid.UUID) -> Badge:
        """Creates a new badge for a participant with an HMAC signature."""
        from datetime import datetime, timezone as tz
        import logging
        logger = logging.getLogger(__name__)

        serial_number = f"ACCRA-{uuid.uuid4().hex[:8].upper()}"
        # Explicitly set created_at so it is never None before flush
        now = datetime.now(tz.utc).replace(tzinfo=None)
        issued_at = int(now.replace(tzinfo=tz.utc).timestamp())
        qr_hmac = self.generate_signature(str(participant_id), serial_number, issued_at)

        badge = Badge(
            participant_id=participant_id,
            serial_number=serial_number,
            qr_hmac=qr_hmac,
            status="active",
            created_at=now
        )
        
        try:
            self.session.add(badge)
            await self.session.commit()
            await self.session.refresh(badge)
            return badge
        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(f"Badge IntegrityError for participant {participant_id}: {e}")
            raise ValueError("A badge already exists for this participant.")
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Badge creation failed for participant {participant_id}: {e}")
            raise

    async def create_badges_batch(self, participant_ids: list[uuid.UUID]) -> list[Badge]:
        """Creates multiple badges in a single transaction."""
        badges = []
        for pid in participant_ids:
            serial_number = f"ACCRA-{uuid.uuid4().hex[:8].upper()}"
            badges.append(Badge(
                participant_id=pid,
                serial_number=serial_number,
                status="active"
            ))
        try:
            self.session.add_all(badges)
            await self.session.flush()
            for b in badges:
                issued_at = int(b.created_at.replace(tzinfo=timezone.utc).timestamp())
                b.qr_hmac = self.generate_signature(str(b.participant_id), b.serial_number, issued_at)
            await self.session.commit()
            for b in badges:
                await self.session.refresh(b)
            return badges
        except IntegrityError:
            await self.session.rollback()
            raise ValueError("One or more participants already have badges.")

    async def update_badge_status(self, badge_id: uuid.UUID, status: str) -> Badge:
        badge = await self.session.get(Badge, badge_id)
        if not badge:
            raise ValueError("Badge not found")
        badge.status = status
        await self.session.commit()
        await self.session.refresh(badge)
        
        # Instantly invalidate scanner cache for this participant
        if self.redis:
            cache_pattern = f"auth:{badge.participant_id}:*"
            keys = await self.redis.keys(cache_pattern)
            if keys:
                await self.redis.delete(*keys)
                
        return badge

    def generate_qr_code(self, badge: Badge) -> str:
        """Generates a base64 encoded PNG of the QR code."""
        issued_at = int(badge.created_at.replace(tzinfo=timezone.utc).timestamp())
        qr_data = json.dumps({
            "participant_id": str(badge.participant_id),
            "serial_number": badge.serial_number,
            "issued_at": issued_at,
            "signature": badge.qr_hmac
        })

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        
        return base64.b64encode(buffered.getvalue()).decode("utf-8")