import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
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

allow_badge_generate_roles = RoleChecker(["admin", "officer", "org_admin"])
allow_badge_revoke_roles = RoleChecker(["admin", "officer"])

class BatchBadgeRequest(BaseModel):
    participant_ids: List[uuid.UUID]

@router.post("/{reference_id}", status_code=201, summary="Generate Badge (Single)")
async def generate_badge(
    reference_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_badge_generate_roles)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Generates the cryptographic signature, QR code, and assigns a Serial Number to an approved participant.
    (Note: `reference_id` can be either the Participant ID or the original Application ID).
    Automatically triggers an email to the user with a download link.
    """
    # Rate Limiting: Max 30 single badge generations per minute per user
    rate_limit_key = f"rate_limit:badge_single:{current_user.id}"
    requests_made = await redis.incr(rate_limit_key)
    if requests_made == 1:
        await redis.expire(rate_limit_key, 60)  # 60-second window
        
    if requests_made > 30:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many badge generations. Please wait a minute.")

    # Resolve ID: Frontend might pass an Application ID instead of a Participant ID
    stmt = select(Participant).where((Participant.id == reference_id) | (Participant.application_id == reference_id))
    participant = (await db.execute(stmt)).scalars().first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found. Ensure the application is approved.")
        
    # SECURITY CHECK: org_admin can only generate badges for their own team
    if str(current_user.role) == "org_admin" and participant.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to generate badges for participants outside your organization.")

    participant_id = participant.id

    service = BadgeService(db)
    
    try:
        badge = await service.create_badge(participant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    qr_base64 = service.generate_qr_code(badge)
    
    # Fetch the participant's email and first name from the linked Application
    stmt = (
        select(Application.first_name, Application.email, Application.preferred_language)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .where(Participant.id == participant_id)
    )
    row = (await db.execute(stmt)).first()
    if row:
        first_name, email, language = row
        download_link = f"{settings.FRONTEND_URL}/badges/download/{participant_id}"
        send_email_notification.delay(
            recipient_email=email,
            template_key="badge_ready",
            language=language or 'en',
            context={"first_name": first_name, "download_link": download_link}
        )
    
    return {
        "badge_id": badge.id,
        "serial_number": badge.serial_number,
        "qr_image_base64": f"data:image/png;base64,{qr_base64}"
    }

@router.post("/batch/generate", status_code=201, summary="Generate Badges (Bulk)")
async def generate_badges_batch(
    request: BatchBadgeRequest,
    current_user: Annotated[User, Depends(allow_badge_generate_roles)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Generates badges for an array of participant/application IDs.
    Useful when an Admin highlights multiple rows in the data table and clicks "Generate Badges".
    """
    # Rate Limiting: Max 10 bulk generations per minute per user
    rate_limit_key = f"rate_limit:badge_batch:{current_user.id}"
    requests_made = await redis.incr(rate_limit_key)
    if requests_made == 1:
        await redis.expire(rate_limit_key, 60)  # 60-second window
        
    if requests_made > 10:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many batch badge generations. Please wait a minute.")

    # Resolve all IDs (handles both Participant IDs and Application IDs)
    stmt = select(Participant).where(
        (Participant.id.in_(request.participant_ids)) | 
        (Participant.application_id.in_(request.participant_ids))
    )
    participants = list((await db.execute(stmt)).scalars().all())

    # SECURITY CHECK: org_admin can only generate badges for their own team
    if str(current_user.role) == "org_admin":
        for p in participants:
            if p.organization_id != current_user.organization_id:
                raise HTTPException(status_code=403, detail="Not authorized to generate badges for participants outside your organization.")

    resolved_ids = [p.id for p in participants]

    service = BadgeService(db)
    try:
        badges = await service.create_badges_batch(resolved_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Fetch all participants' emails and send notifications in bulk
    stmt = (
        select(Participant.id, Application.first_name, Application.email, Application.preferred_language)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .where(Participant.id.in_(resolved_ids))
    )
    rows = (await db.execute(stmt)).all()
    for pid, first_name, email, language in rows:
        download_link = f"{settings.FRONTEND_URL}/badges/download/{pid}"
        send_email_notification.delay(
            recipient_email=email,
            template_key="badge_ready_bulk",
            language=language or 'en',
            context={"first_name": first_name, "download_link": download_link}
        )
        
    result = []
    for badge in badges:
        raw_base64 = service.generate_qr_code(badge)
        result.append({
            "badge_id": badge.id,
            "serial_number": badge.serial_number,
            "qr_image_base64": f"data:image/png;base64,{raw_base64}"
        })
    return result

@router.patch("/{badge_id}/status", response_model=BadgeRead, status_code=200, summary="Update Badge Status (Revoke)")
async def update_badge_status(
    badge_id: uuid.UUID,
    update_in: BadgeUpdate,
    current_user: Annotated[User, Depends(allow_badge_revoke_roles)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    If status is changed to `revoked`, this instantly invalidates all Redis cache keys globally for this participant,
    locking them out of the venue immediately.
    """
    service = BadgeService(db, redis=redis)
    try:
        badge = await service.update_badge_status(badge_id, update_in.status)
        # 🔒 ZERO-TRUST: O(1) participant cache invalidation
        if update_in.status.lower() == "revoked":
            await redis.incr(f"participant_version:{badge.participant_id}")
        return badge
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{reference_id}/data", status_code=200, summary="Get Raw Badge Data (For Frontend PDF Generation)")
async def get_badge_data(
    reference_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all the raw data required for the frontend to render the PDF badge directly in the browser.
    """
    stmt = (
        select(Participant, Application.user_id, Application.organization_id)
        .join(Application, Participant.application_id == Application.id)
        .where((Participant.id == reference_id) | (Participant.application_id == reference_id))
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Participant not found. Ensure the application is approved.")
        
    participant, app_user_id, app_org_id = row
    
    # SECURITY: Ensure applicants can only download their own badges, and Org Admins only their team's.
    if str(current_user.role) == "applicant" and app_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this badge data.")
    if str(current_user.role) == "org_admin" and app_org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this badge data.")
    if str(current_user.role) == "scanner":
        raise HTTPException(status_code=403, detail="Scanner accounts cannot download badge data.")
        
    # 1. Fetch Badge
    stmt = select(Badge).where(Badge.participant_id == participant.id)
    badge = (await db.execute(stmt)).scalar_one_or_none()
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found. Please generate the badge first.")

    # 2. Fetch User details
    stmt = (
        select(User.first_name, User.last_name, Application.category, Application.photo_url, Application.country, Participant.role)
        .select_from(Participant)
        .join(Application, Participant.application_id == Application.id)
        .join(User, Application.user_id == User.id)
        .where(Participant.id == participant.id)
    )
    row = (await db.execute(stmt)).first()
    first_name, last_name, category, photo_url, country, role = row
    
    service = BadgeService(db)
    qr_base64 = service.generate_qr_code(badge)
    
    return {
        "participant_name": f"{first_name} {last_name}",
        "role": role,
        "category": category,
        "country": country,
        "photo_url": photo_url,
        "serial_number": badge.serial_number,
        "qr_image_base64": f"data:image/png;base64,{qr_base64}"
    }