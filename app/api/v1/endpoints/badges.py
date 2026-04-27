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
from app.api.deps import get_current_user, RoleChecker, RateLimiter
from app.models.user import User
from app.models.participant import Participant
from app.models.application import Application
from app.models.badge import Badge
from app.models.audit_log import AuditLog
from app.models.zone import Zone
from app.models.zone_access import ZoneAccess
from app.workers.main import send_email_notification
from app.config.settings import settings

router = APIRouter()

allow_badge_generate_roles = RoleChecker(["admin", "officer", "org_admin"])
allow_badge_revoke_roles = RoleChecker(["admin", "officer"])

class BatchBadgeRequest(BaseModel):
    participant_ids: List[uuid.UUID]

# ⚠️ IMPORTANT: /batch/generate MUST be defined BEFORE /{reference_id}
# to prevent FastAPI matching "batch" as a UUID reference_id.
@router.post("/batch/generate", status_code=201, summary="Generate Badges (Bulk)", dependencies=[Depends(RateLimiter(requests=10, window=60))])
async def generate_badges_batch(
    request: BatchBadgeRequest,
    current_user: Annotated[User, Depends(allow_badge_generate_roles)],
    db: AsyncSession = Depends(get_db)
):
    """
    Generates badges for an array of participant/application IDs.
    Useful when an Admin highlights multiple rows in the data table and clicks "Generate Badges".
    """

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

@router.post("/{reference_id}", status_code=201, summary="Generate Badge (Single)", dependencies=[Depends(RateLimiter(requests=30, window=60))])
async def generate_badge(
    reference_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_badge_generate_roles)],
    db: AsyncSession = Depends(get_db)
):
    """
    Generates the cryptographic signature, QR code, and assigns a Serial Number to an approved participant.
    (Note: `reference_id` can be either the Participant ID or the original Application ID).
    Automatically triggers an email to the user with a download link.
    """

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
        try:
            badge = await service.create_badge(participant_id)
        except ValueError:
            # Idempotent behavior: If badge already exists, just fetch it instead of failing
            stmt = select(Badge).where(Badge.participant_id == participant_id)
            badge = (await db.execute(stmt)).scalar_one_or_none()
            if not badge:
                raise HTTPException(status_code=500, detail="Badge generation failed internally (not found after rollback).")
            
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
            # Only send email if the badge was newly generated (optional, but good practice)
            # We can just send it anyway as a resend, or we can assume if they hit POST it's fine.
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
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)} | Trace: {traceback.format_exc()}")

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
            
        audit = AuditLog(entity_type="badge", entity_id=badge_id, action="badge_status_change", new_value=update_in.status.value, user_id=current_user.id)
        db.add(audit)
        await db.commit()
        
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
    Includes the full application fields, allowed access zones (with zone name, code, and color),
    and the base64-encoded QR code image.
    """
    stmt = (
        select(Participant, Application)
        .join(Application, Participant.application_id == Application.id)
        .where((Participant.id == reference_id) | (Participant.application_id == reference_id))
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Participant not found. Ensure the application is approved.")
        
    participant, application = row
    
    # SECURITY: Ensure applicants can only download their own badges, and Org Admins only their team's.
    if str(current_user.role) == "applicant" and application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this badge data.")
    if str(current_user.role) == "org_admin" and application.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this badge data.")
    if str(current_user.role) == "scanner":
        raise HTTPException(status_code=403, detail="Scanner accounts cannot download badge data.")
        
    # 1. Fetch Badge
    stmt = select(Badge).where(Badge.participant_id == participant.id)
    badge = (await db.execute(stmt)).scalar_one_or_none()
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found. Please generate the badge first.")

    # 2. Resolve allowed zones via the participant's category
    zones_allowed = []
    if participant.category_id:
        zone_stmt = (
            select(Zone.id, Zone.name, Zone.code, Zone.color, Zone.description, Zone.require_qr_scan)
            .join(ZoneAccess, ZoneAccess.zone_id == Zone.id)
            .where(
                ZoneAccess.category_id == participant.category_id,
                Zone.is_active == True
            )
        )
        zone_rows = (await db.execute(zone_stmt)).all()
        zones_allowed = [
            {
                "id": str(z.id),
                "name": z.name,
                "code": z.code,
                "color": z.color,
                "description": z.description,
                "require_qr_scan": z.require_qr_scan
            }
            for z in zone_rows
        ]

    # 3. Generate QR code
    service = BadgeService(db)
    qr_base64 = service.generate_qr_code(badge)

    return {
        # --- Full Application Fields ---
        "tournament_id": application.tournament_id,
        "user_id": application.user_id,
        "first_name": application.first_name,
        "last_name": application.last_name,
        "email": application.email,
        "phone_number": application.phone_number,
        "passport_number": application.passport_number,
        "specific_role": application.specific_role,
        "emergency_contact_name": application.emergency_contact_name,
        "emergency_contact_phone": application.emergency_contact_phone,
        "special_requirements": application.special_requirements,
        "organization_id": application.organization_id,
        "category": application.category,
        "outlet_name": application.outlet_name,
        "media_accreditation_type": application.media_accreditation_type,
        "photo_url": application.photo_url,
        "dob": str(application.dob) if application.dob else None,
        "gender": application.gender,
        "country": application.country,
        "preferred_language": application.preferred_language,
        "sporting_disciplines": application.sporting_disciplines or [],
        "id": str(participant.id),
        "status": application.status,
        "submitted_at": application.submitted_at,
        "created_at": application.created_at,
        "reviewer_comments": application.reviewer_comments,
        "reviewer_id": application.reviewer_id,
        # --- Badge-Specific Fields ---
        "badge_id": str(badge.id),
        "serial_number": badge.serial_number,
        "participant_role": participant.role,
        # --- Zone Access ---
        "zones_allowed": zones_allowed,
        # --- QR Code ---
        "qr_image_base64": f"data:image/png;base64,{qr_base64}"
    }