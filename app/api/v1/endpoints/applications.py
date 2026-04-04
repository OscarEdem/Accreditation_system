import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationReview, ApplicationReadWithSubmitter, ApplicationListResponse
from app.services.application import ApplicationService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.workers.main import send_email_notification

router = APIRouter()

allow_review_roles = RoleChecker(["admin", "officer"])

def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)

@router.post("/", response_model=ApplicationRead, status_code=201)
async def create_application(
    application_in: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service)
):
    is_privileged = current_user.role in ["admin", "loc_admin", "officer", "org_admin"]
    
    # Force the application to belong to the logged-in user to prevent impersonation (unless admin)
    if not is_privileged:
        application_in.user_id = current_user.id
    else:
        application_in.user_id = application_in.user_id or current_user.id
        
    return await service.create_application(application_in, bypass_duplicate_check=is_privileged)

@router.get("/", response_model=ApplicationListResponse)
async def get_applications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status (e.g., pending, approved)"),
    category: str | None = Query(None, description="Filter by category"),
    organization_id: uuid.UUID | None = Query(None, description="Filter by organization ID"),
    sort_desc: bool = Query(True, description="Sort by submitted_at descending")
):
    skip = (page - 1) * limit
    
    # Resolve user filter constraint: admins see all, applicants see their own
    user_id_filter = None if current_user.role in ["admin", "loc_admin", "officer"] else current_user.id
    
    items, total = await service.get_applications(
        user_id=user_id_filter,
        status=status,
        category=category,
        organization_id=organization_id,
        skip=skip, 
        limit=limit,
        sort_desc=sort_desc
    )
        
    return {"total": total, "items": items}

@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service)
):
    return await service.get_application_by_id(application_id)

@router.put("/{application_id}/review", response_model=ApplicationRead)
async def review_application(
    application_id: uuid.UUID,
    review_in: ApplicationReview,
    current_user: Annotated[User, Depends(allow_review_roles)],
    service: ApplicationService = Depends(get_application_service),
    db: AsyncSession = Depends(get_db)
):
    application = await service.review_application(application_id, current_user.id, review_in)
    
    # Automatically trigger a Celery background email if the application is approved
    if review_in.status.lower() == "approved":
        user = await db.get(User, application.user_id)
        if user:
            send_email_notification.delay(
                recipient_email=user.email,
                subject="Your Accreditation Application is Approved!",
                body=f"Congratulations {user.first_name}, your application for category {application.category} has been approved."
            )
            
    return application