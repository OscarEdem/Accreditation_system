import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.services.badge import BadgeService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.participant import Participant
from app.models.application import Application
from app.models.badge import Badge

router = APIRouter()

# Only admins and accreditation officers should be able to generate badges
allow_badge_roles = RoleChecker(["admin", "officer"])

@router.post("/{participant_id}", status_code=201)
async def generate_badge(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_badge_roles)],
    db: AsyncSession = Depends(get_db)
):
    service = BadgeService(db)
    
    try:
        badge = await service.create_badge(participant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    qr_base64 = service.generate_qr_code(badge)
    
    return {
        "badge_id": badge.id,
        "serial_number": badge.serial_number,
        "qr_image_base64": qr_base64
    }

@router.get("/{participant_id}/pdf", status_code=200)
async def download_badge_pdf(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_badge_roles)],
    db: AsyncSession = Depends(get_db)
):
    service = BadgeService(db)
    
    # 1. Fetch the generated Badge
    stmt = select(Badge).where(Badge.participant_id == participant_id)
    badge = (await db.execute(stmt)).scalar_one_or_none()
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found. Please generate the badge first.")

    # 2. Fetch Participant, Application, and User details
    stmt = (
        select(User.first_name, User.last_name, Application.category, Application.photo_url)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .join(User, Application.user_id == User.id)
        .where(Participant.id == participant_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Participant details not found.")

    first_name, last_name, category, photo_url = row
    pdf_bytes = await service.generate_pdf_badge(badge, photo_url, f"{first_name} {last_name}", category)
    
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="badge_{badge.serial_number}.pdf"'})