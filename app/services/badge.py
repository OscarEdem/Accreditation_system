import os
import hmac
import hashlib
import json
import uuid
import base64
import qrcode
import httpx
from datetime import datetime, timezone
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from redis.asyncio import Redis
from app.config.settings import settings
from app.models.badge import Badge

# In-memory cache for the PDF template to prevent disk I/O on every generation
_TEMPLATE_CACHE: bytes | None = None
_PHOTO_CACHE: dict[str, bytes] = {}
_PHOTO_CACHE_LAST_CLEARED: datetime = datetime.now(timezone.utc)

class BadgeService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None):
        self.session = session
        self.redis = redis

    def generate_signature(self, participant_id: str, serial_number: str) -> str:
        """Generates an HMAC SHA-256 signature for the badge data."""
        message = f"{participant_id}:{serial_number}".encode("utf-8")
        secret = settings.SECRET_KEY.encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    async def create_badge(self, participant_id: uuid.UUID) -> Badge:
        """Creates a new badge for a participant with an HMAC signature."""
        serial_number = f"ACCRA-{uuid.uuid4().hex[:8].upper()}"
        signature = self.generate_signature(str(participant_id), serial_number)

        badge = Badge(
            participant_id=participant_id,
            serial_number=serial_number,
            qr_hmac=signature,
            status="active"
        )
        
        try:
            self.session.add(badge)
            await self.session.commit()
            await self.session.refresh(badge)
            return badge
        except IntegrityError:
            await self.session.rollback()
            raise ValueError("A badge already exists for this participant.")

    async def create_badges_batch(self, participant_ids: list[uuid.UUID]) -> list[Badge]:
        """Creates multiple badges in a single transaction."""
        badges = []
        for pid in participant_ids:
            serial_number = f"ACCRA-{uuid.uuid4().hex[:8].upper()}"
            signature = self.generate_signature(str(pid), serial_number)
            badges.append(Badge(
                participant_id=pid,
                serial_number=serial_number,
                qr_hmac=signature,
                status="active"
            ))
        try:
            self.session.add_all(badges)
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
        qr_data = json.dumps({
            "participant_id": str(badge.participant_id),
            "serial_number": badge.serial_number,
            "signature": badge.qr_hmac
        })

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    async def generate_pdf_badge(self, badge: Badge, photo_url: str | None, participant_name: str, category: str, country: str, role: str) -> bytes:
        """Generates a PDF badge by overlaying user data onto the pre-designed PDF template."""
        # Use the exact dimensions from the provided Illustrator PDF template (4.1 x 5.8 inches)
        width, height = 295.2, 417.6
        
        # 1. Create a transparent overlay with ReportLab
        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(width, height))

        # Define layout configuration to avoid magic numbers
        LAYOUT = {
            "photo": {"x": 0.6, "y_offset": 2.7, "size": 1.8},
            "text": {"x_ratio": 0.68, "y_name_offset": 2.6, "y_category_offset": 2.95, "y_country_offset": 3.2, "max_width": 1.8},
            "qr": {"y": 0.9, "size": 1.4},
            "serial": {"y": 0.65}
        }
        
        # Role-based color mapping (RGB values 0.0 to 1.0)
        ROLE_COLORS = {
            "athlete": (0.12, 0.33, 0.61),    # Blue
            "media": (0.85, 0.20, 0.20),      # Red
            "loc": (0.18, 0.55, 0.22),        # Green
            "technical": (0.90, 0.50, 0.10),  # Orange
            "vip": (0.55, 0.20, 0.65),        # Purple
        }
        
        cat_r, cat_g, cat_b = 0, 0, 0  # Default Black
        for key, color in ROLE_COLORS.items():
            if key in role.lower() or key in category.lower():
                cat_r, cat_g, cat_b = color
                break

        # Draw Participant Photo
        if photo_url:
            global _PHOTO_CACHE, _PHOTO_CACHE_LAST_CLEARED
            
            # Automatically clear the local photo cache every 24 hours (86400 seconds)
            now = datetime.now(timezone.utc)
            if (now - _PHOTO_CACHE_LAST_CLEARED).total_seconds() > 86400:
                _PHOTO_CACHE.clear()
                _PHOTO_CACHE_LAST_CLEARED = now
                
            photo_bytes = _PHOTO_CACHE.get(photo_url)
            
            if not photo_bytes:
                async with httpx.AsyncClient() as client:
                    response = await client.get(photo_url)
                    if response.status_code == 200:
                        photo_bytes = response.content
                        # Prevent unbounded memory growth by capping the cache at 200 photos
                        if len(_PHOTO_CACHE) >= 200:
                            _PHOTO_CACHE.pop(next(iter(_PHOTO_CACHE)))
                        _PHOTO_CACHE[photo_url] = photo_bytes
            
            if photo_bytes:
                photo_io = BytesIO(photo_bytes)
                photo_img = ImageReader(photo_io)
                
                # Left-side photo box
                photo_x = LAYOUT["photo"]["x"] * inch
                photo_y = height - LAYOUT["photo"]["y_offset"] * inch
                photo_size = LAYOUT["photo"]["size"] * inch
                
                c.drawImage(
                    photo_img,
                    photo_x,
                    photo_y,
                    width=photo_size,
                    height=photo_size,
                    preserveAspectRatio=True,
                    anchor='c'
                )

        # Right-side text column (Name is always drawn in Black)
        c.setFillColorRGB(0, 0, 0)
        text_center_x = width * LAYOUT["text"]["x_ratio"]
        
        # NAME (big + bold)
        name_font = "Helvetica-Bold"
        name_size = 16
        max_width = LAYOUT["text"]["max_width"] * inch
        
        while c.stringWidth(participant_name, name_font, name_size) > max_width and name_size > 9:
            name_size -= 1
            
        c.setFont(name_font, name_size)
        c.drawCentredString(text_center_x, height - LAYOUT["text"]["y_name_offset"] * inch, participant_name)
        
        # Switch to the role-specific color for Category and Country
        c.setFillColorRGB(cat_r, cat_g, cat_b)

        # CATEGORY
        c.setFont("Helvetica", 11)
        c.drawCentredString(text_center_x, height - LAYOUT["text"]["y_category_offset"] * inch, category.upper())

        # COUNTRY
        c.setFont("Helvetica-Oblique", 11)
        c.drawCentredString(text_center_x, height - LAYOUT["text"]["y_country_offset"] * inch, country.upper())

        # Reset back to black for the QR & Serial Number
        c.setFillColorRGB(0, 0, 0)

        # QR Code (BOTTOM CENTER)
        qr_base64 = self.generate_qr_code(badge)
        qr_img = ImageReader(BytesIO(base64.b64decode(qr_base64)))
        qr_size = LAYOUT["qr"]["size"] * inch
        qr_x = (width - qr_size) / 2
        qr_y = LAYOUT["qr"]["y"] * inch
        c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)

        # Serial Number (just below QR)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(width / 2, LAYOUT["serial"]["y"] * inch, badge.serial_number)

        c.showPage()
        c.save()
        overlay_buffer.seek(0)
        
        global _TEMPLATE_CACHE
        if _TEMPLATE_CACHE is None:
            # Calculate the absolute path to the project root to reliably find the PDF on AWS
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            template_path = os.path.join(root_dir, "accreditation.pdf")
            with open(template_path, "rb") as f:
                _TEMPLATE_CACHE = f.read()
        
        # 2. Merge the overlay with the original PDF template
        template_reader = PdfReader(BytesIO(_TEMPLATE_CACHE))
        template_page = template_reader.pages[0]  # The front design page
        
        overlay_reader = PdfReader(overlay_buffer)
        overlay_page = overlay_reader.pages[0]
        
        # Stamp the dynamic data onto the template
        template_page.merge_page(overlay_page)
        
        writer = PdfWriter()
        writer.add_page(template_page)
        
        # If your template has a back page (Rules/Terms), append it to the final download!
        if len(template_reader.pages) > 1:
            writer.add_page(template_reader.pages[1])
            
        final_buffer = BytesIO()
        writer.write(final_buffer)
        return final_buffer.getvalue()