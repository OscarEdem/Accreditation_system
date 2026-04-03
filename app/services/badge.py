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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.config.settings import settings
from app.models.badge import Badge

class BadgeService:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def generate_pdf_badge(self, badge: Badge, photo_url: str | None, participant_name: str, category: str) -> bytes:
        """Generates a CR80 size PDF badge including photo, text, and QR code."""
        buffer = BytesIO()
        # CR80 dimensions: 2.125 x 3.375 inches
        width, height = 2.125 * inch, 3.375 * inch
        c = canvas.Canvas(buffer, pagesize=(width, height))

        # 1. Header (Background and Title)
        c.setFillColorRGB(0.1, 0.1, 0.4)
        c.rect(0, height - 0.5 * inch, width, 0.5 * inch, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, height - 0.3 * inch, "ACCRA 2026")

        # 2. Participant Photo
        if photo_url:
            async with httpx.AsyncClient() as client:
                response = await client.get(photo_url)
                if response.status_code == 200:
                    photo_io = BytesIO(response.content)
                    photo_img = ImageReader(photo_io)
                    # Draw photo centered below the header
                    c.drawImage(photo_img, (width - 1.2 * inch) / 2, height - 1.8 * inch, width=1.2 * inch, height=1.2 * inch, preserveAspectRatio=True)

        # 3. Participant Info
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(width / 2, height - 2.1 * inch, participant_name)
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2, height - 2.3 * inch, category.upper())

        # 4. HMAC QR Code
        qr_base64 = self.generate_qr_code(badge)
        qr_img = ImageReader(BytesIO(base64.b64decode(qr_base64)))
        c.drawImage(qr_img, (width - 1 * inch) / 2, 0.1 * inch, width=1 * inch, height=1 * inch)

        c.showPage()
        c.save()
        return buffer.getvalue()