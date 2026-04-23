import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.schemas.participant import ParticipantRead, ParticipantListResponse
from app.services.participant import ParticipantService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.application import Application
from app.models.organization import Organization

router = APIRouter()

allow_read_participants = RoleChecker(["admin", "loc_admin", "officer", "org_admin", "applicant"])

def get_participant_service(db: AsyncSession = Depends(get_db)) -> ParticipantService:
    return ParticipantService(db)

@router.get("/", response_model=ParticipantListResponse, summary="List Participants (Paginated)")
async def get_participants(
    current_user: Annotated[User, Depends(allow_read_participants)],
    service: ParticipantService = Depends(get_participant_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=500, description="Items per page"),
    tournament_id: uuid.UUID | None = Query(None, description="Filter by tournament ID"),
    role: str | None = Query(None, description="Filter by role"),
    organization_id: uuid.UUID | None = Query(None, description="Filter by organization ID"),
    category: str | None = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch a list of fully approved participants. Use this for the Participants table in the admin dashboard.
    """
    skip = (page - 1) * limit
    
    # Security: Prevent IDOR on list fetching
    user_id_filter = None
    org_id_filter = organization_id # Default to the requested query filter for Super Admins
    category_filter = category
    
    if str(current_user.role) == "applicant":
        user_id_filter = current_user.id
    elif str(current_user.role) == "org_admin":
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Org Admin account is not associated with an organization.")
        org = await db.get(Organization, current_user.organization_id)
        if org and org.type == "Media":
            org_id_filter = None
            category_filter = "Media"
        else:
            org_id_filter = current_user.organization_id # Forcibly override to prevent tenant escape
        
    items, total = await service.get_participants(
        tournament_id=tournament_id,
        role=role,
        organization_id=org_id_filter,
        user_id=user_id_filter,
        category=category_filter,
        skip=skip, 
        limit=limit
    )
    return {"total": total, "items": items}

@router.get("/{participant_id}", response_model=ParticipantRead)
async def get_participant(
    participant_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_read_participants)],
    service: ParticipantService = Depends(get_participant_service),
    db: AsyncSession = Depends(get_db)
):
    participant = await service.get_participant_by_id(participant_id)
    
    # SECURITY: Prevent IDOR. Enforce strict ownership boundaries.
    if str(current_user.role) == "applicant" and participant.application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this participant.")
            
    if str(current_user.role) == "org_admin":
        org = await db.get(Organization, current_user.organization_id)
        is_media_admin = org and org.type == "Media"
        if participant.organization_id != current_user.organization_id:
            if not (is_media_admin and participant.application.category == "Media"):
                raise HTTPException(status_code=403, detail="Not authorized to view this participant.")
        
    return participant