import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.badge import BadgeUpdate, BadgeRead
from app.services.badge import BadgeService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.participant import Participant
from app.models.application import Application
from app.models.badge import Badge
from app.workers.main import send_email_notification
from app.config.settings import settings

router = APIRouter()

# Only admins and accreditation officers should be able to generate badges
allow_badge_roles = RoleChecker(["admin", "officer"])

class BatchBadgeRequest(BaseModel):
    participant_ids: List[uuid.UUID]

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
    
    # Fetch the participant's email and first name from the linked Application
    stmt = (
        select(Application.first_name, Application.email)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .where(Participant.id == participant_id)
    )
    row = (await db.execute(stmt)).first()
    if row:
        first_name, email = row
        download_link = f"{settings.FRONTEND_URL}/badges/download/{participant_id}"
        send_email_notification.delay(
            recipient_email=email,
            subject="Your ACCRA 2026 Badge is Ready!",
            body=f"Hello {first_name},\n\nYour official ACCRA 2026 accreditation badge has been generated.\n\nYou can download and print your PDF badge here:\n{download_link}\n\nPlease bring this with you to the venue."
        )
    
    return {
        "badge_id": badge.id,
        "serial_number": badge.serial_number,
        "qr_image_base64": qr_base64
    }

@router.post("/batch/generate", status_code=201)
async def generate_badges_batch(
    request: BatchBadgeRequest,
    current_user: Annotated[User, Depends(allow_badge_roles)],
    db: AsyncSession = Depends(get_db)
):
    service = BadgeService(db)
    try:
        badges = await service.create_badges_batch(request.participant_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Fetch all participants' emails and send notifications in bulk
    stmt = (
        select(Participant.id, Application.first_name, Application.email)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .where(Participant.id.in_(request.participant_ids))
    )
    rows = (await db.execute(stmt)).all()
    for pid, first_name, email in rows:
        download_link = f"{settings.FRONTEND_URL}/badges/download/{pid}"
        send_email_notification.delay(
            recipient_email=email,
            subject="Your ACCRA 2026 Badge is Ready!",
            body=f"Hello {first_name},\n\nYour official ACCRA 2026 accreditation badge has been generated in bulk by your organization.\n\nYou can download your PDF badge here:\n{download_link}\n\nPlease bring this with you to the venue."
        )
        
    result = []
    for badge in badges:
        result.append({
            "badge_id": badge.id,
            "serial_number": badge.serial_number,
            "qr_image_base64": service.generate_qr_code(badge)
        })
    return result

@router.patch("/{badge_id}/status", response_model=BadgeRead, status_code=200)
async def update_badge_status(
    badge_id: uuid.UUID,
    update_in: BadgeUpdate,
    current_user: Annotated[User, Depends(allow_badge_roles)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    service = BadgeService(db, redis=redis)
    try:
        return await service.update_badge_status(badge_id, update_in.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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