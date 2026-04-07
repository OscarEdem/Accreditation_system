import os
import hmac
import hashlib
import json
import uuid
import base64
import qrcode
import httpx
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

    async def generate_pdf_badge(self, badge: Badge, photo_url: str | None, participant_name: str, category: str, country: str) -> bytes:
        """Generates a PDF badge by overlaying user data onto the pre-designed PDF template."""
        # Use the exact dimensions from the provided Illustrator PDF template (4.1 x 5.8 inches)
        width, height = 295.2, 417.6
        
        # 1. Create a transparent overlay with ReportLab
        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(width, height))

        # Draw Participant Photo
        if photo_url:
            async with httpx.AsyncClient() as client:
                response = await client.get(photo_url)
                if response.status_code == 200:
                    photo_io = BytesIO(response.content)
                    photo_img = ImageReader(photo_io)
                    # Place photo in the upper/middle section (adjust inches to fit your design boxes)
                    c.drawImage(photo_img, (width - 1.5 * inch) / 2, height - 2.5 * inch, width=1.5 * inch, height=1.5 * inch, preserveAspectRatio=True)

        # Draw Participant Info with Dynamic Font Scaling for Long Names
        c.setFillColorRGB(0, 0, 0)
        
        name_font = "Helvetica-Bold"
        name_size = 18  # Increased starting font size (was 14)
        max_width = width - 0.4 * inch  # Leave a 0.2-inch safety margin on both sides
        
        while c.stringWidth(participant_name, name_font, name_size) > max_width and name_size > 8:
            name_size -= 1
            
        c.setFont(name_font, name_size)
        c.drawCentredString(width / 2, height - 2.8 * inch, participant_name)
        
        c.setFont("Helvetica", 11)
        c.drawCentredString(width / 2, height - 3.05 * inch, category.upper())

        c.setFont("Helvetica-Oblique", 11)
        c.drawCentredString(width / 2, height - 3.3 * inch, country.upper())

        # Draw HMAC QR Code
        qr_base64 = self.generate_qr_code(badge)
        qr_img = ImageReader(BytesIO(base64.b64decode(qr_base64)))
        # Place QR code near the bottom center (above the serial number)
        c.drawImage(qr_img, (width - 1.5 * inch) / 2, 0.7 * inch, width=1.5 * inch, height=1.5 * inch)

        # Draw Serial Number
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(width / 2, 0.5 * inch, badge.serial_number)

        c.showPage()
        c.save()
        overlay_buffer.seek(0)
        
        # Calculate the absolute path to the project root to reliably find the PDF on AWS
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(root_dir, "accreditation.pdf")
        
        # 2. Merge the overlay with the original PDF template
        template_reader = PdfReader(template_path)
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