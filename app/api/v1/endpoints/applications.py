import uuid
import csv
import io
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationReview, ApplicationBatchReview, ApplicationReadWithSubmitter, ApplicationListResponse, ApplicationTrackResponse
from app.schemas.document import DocumentReview, DocumentRead
from app.services.application import ApplicationService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.workers.main import send_email_notification
from app.models.category import Category
from app.models.tournament import Tournament
from app.services.organization import OrganizationService
from app.core.constants import ORG_ALLOWED_CATEGORIES

router = APIRouter()

allow_review_roles = RoleChecker(["admin", "officer"])

def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)

@router.post("/public", response_model=ApplicationRead, status_code=201, summary="Submit Public Application")
async def submit_public_application(
    application_in: ApplicationCreate,
    service: ApplicationService = Depends(get_application_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for applicants to submit their application without needing a JWT token.
    
    **Frontend Implementation Notes:**
    - Used at the end of the public multi-step form wizard.
    - `category` must exactly match one of the system's allowed category strings.
    - `organization_id` must be provided if the user belongs to a specific team (e.g., Team Ghana).
    - `tournament_id` is optional. If omitted, the system will auto-assign the active tournament.
    
    **Example JSON Payload:**
    ```json
    {
      "first_name": "John",
      "last_name": "Doe",
      "category": "Athlete"
    }
    ```
    """
    category_exists = await db.scalar(select(Category).where(Category.name == application_in.category.value))
    if not category_exists:
        raise HTTPException(status_code=400, detail=f"Category '{application_in.category.value}' does not exist in the system.")

    if not application_in.tournament_id:
        active_tourn = await db.scalar(select(Tournament).where(Tournament.is_active == True).order_by(Tournament.created_at.desc()).limit(1))
        if not active_tourn:
            raise HTTPException(status_code=400, detail="No active tournament found in the system.")
        application_in.tournament_id = active_tourn.id
    else:
        tournament_exists = await db.scalar(select(Tournament).where(Tournament.id == application_in.tournament_id))
        if not tournament_exists:
            raise HTTPException(status_code=400, detail="Invalid tournament_id. Tournament does not exist.")

    if getattr(application_in, "organization_id", None):
        org_service = OrganizationService(db)
        org = await org_service.get_organization_by_id(application_in.organization_id)
        if not org:
            raise HTTPException(status_code=400, detail="Invalid organization_id. Organization does not exist.")
        if org.name in ORG_ALLOWED_CATEGORIES:
            if application_in.category.value not in ORG_ALLOWED_CATEGORIES[org.name]:
                raise HTTPException(status_code=400, detail=f"Category '{application_in.category.value}' is not allowed for organization '{org.name}'.")

    application_in.user_id = None
    application = await service.create_application(application_in, bypass_duplicate_check=False)
    
    send_email_notification.delay(
        recipient_email=application.email,
        subject="ACCRA 2026 Application Received",
        body=f"Hello {application.first_name},\n\nYour accreditation application for the ACCRA 2026 tournament has been successfully received and is currently under review.\n\nYou will receive another email once a decision has been made."
    )
    
    return application

@router.post("/batch", response_model=List[ApplicationRead], status_code=201, summary="Submit Multiple Applications")
async def create_applications_batch(
    applications_in: List[ApplicationCreate],
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for privileged users (like `org_admin`) to submit multiple applications simultaneously.
    
    **Frontend Implementation Notes:**
    - Pass an array `[]` of application objects in the JSON body.
    - Org Admins bypass duplicate checks, meaning they can submit multiple applications under their own account for their team members.
    """
    if current_user.role not in ["admin", "loc_admin", "officer", "org_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to submit batch applications.")

    # Fetch all valid category names at once to prevent N+1 DB queries in the loop
    valid_categories = set((await db.scalars(select(Category.name))).all())
    valid_tournaments = set((await db.scalars(select(Tournament.id))).all())

    default_tourn = await db.scalar(select(Tournament).where(Tournament.is_active == True).order_by(Tournament.created_at.desc()).limit(1))

    org_service = OrganizationService(db)
    org_cache = {}
    for app_in in applications_in:
        # Force the application to belong to the user's organization if they are an org_admin
        if current_user.role == "org_admin":
            app_in.organization_id = current_user.organization_id

        if app_in.category.value not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Category '{app_in.category.value}' does not exist in the system.")
            
        if not app_in.tournament_id:
            if not default_tourn:
                raise HTTPException(status_code=400, detail="No active tournament found in the system.")
            app_in.tournament_id = default_tourn.id
        elif app_in.tournament_id not in valid_tournaments:
            raise HTTPException(status_code=400, detail="Invalid tournament_id. Tournament does not exist.")

        if getattr(app_in, "organization_id", None):
            if app_in.organization_id not in org_cache:
                org_cache[app_in.organization_id] = await org_service.get_organization_by_id(app_in.organization_id)
            org = org_cache[app_in.organization_id]
            if not org:
                raise HTTPException(status_code=400, detail="Invalid organization_id. Organization does not exist.")
            if org.name in ORG_ALLOWED_CATEGORIES:
                # Admins and Officers can bypass the category restriction
                is_admin = current_user.role in ["admin", "loc_admin", "officer"]
                if app_in.category.value not in ORG_ALLOWED_CATEGORIES[org.name] and not is_admin:
                    raise HTTPException(status_code=400, detail=f"Category '{app_in.category.value}' is not allowed for organization '{org.name}'.")

    applications = await service.create_applications_batch(applications_in, submitter_id=current_user.id)
    
    for app in applications:
        send_email_notification.delay(
            recipient_email=app.email,
            subject="ACCRA 2026 Application Received",
            body=f"Hello {app.first_name},\n\nAn accreditation application for the ACCRA 2026 tournament has been submitted on your behalf by your organization.\n\nYou will receive another email once a decision has been made."
        )
        
    return applications

@router.post("/", response_model=ApplicationRead, status_code=201)
async def create_application(
    application_in: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service),
    db: AsyncSession = Depends(get_db)
):
    # Force the application to belong to the user's organization if they are not system staff
    if current_user.role in ["org_admin", "applicant"]:
        application_in.organization_id = current_user.organization_id

    category_exists = await db.scalar(select(Category).where(Category.name == application_in.category.value))
    if not category_exists:
        raise HTTPException(status_code=400, detail=f"Category '{application_in.category.value}' does not exist in the system.")

    if not application_in.tournament_id:
        active_tourn = await db.scalar(select(Tournament).where(Tournament.is_active == True).order_by(Tournament.created_at.desc()).limit(1))
        if not active_tourn:
            raise HTTPException(status_code=400, detail="No active tournament found in the system.")
        application_in.tournament_id = active_tourn.id
    else:
        tournament_exists = await db.scalar(select(Tournament).where(Tournament.id == application_in.tournament_id))
        if not tournament_exists:
            raise HTTPException(status_code=400, detail="Invalid tournament_id. Tournament does not exist.")

    if getattr(application_in, "organization_id", None):
        org_service = OrganizationService(db)
        org = await org_service.get_organization_by_id(application_in.organization_id)
        if not org:
            raise HTTPException(status_code=400, detail="Invalid organization_id. Organization does not exist.")
        if org.name in ORG_ALLOWED_CATEGORIES:
            # Admins and Officers can bypass the category restriction
            is_admin = current_user.role in ["admin", "loc_admin", "officer"]
            if application_in.category.value not in ORG_ALLOWED_CATEGORIES[org.name] and not is_admin:
                raise HTTPException(status_code=400, detail=f"Category '{application_in.category.value}' is not allowed for organization '{org.name}'.")

    is_privileged = current_user.role in ["admin", "loc_admin", "officer", "org_admin"]
    
    # Force the application to belong to the logged-in user to prevent impersonation (unless admin)
    if not is_privileged:
        application_in.user_id = current_user.id
    else:
        application_in.user_id = application_in.user_id or current_user.id
        
    application = await service.create_application(application_in, bypass_duplicate_check=is_privileged)
    
    send_email_notification.delay(
        recipient_email=application.email,
        subject="ACCRA 2026 Application Received",
        body=f"Hello {application.first_name},\n\nYour accreditation application for the ACCRA 2026 tournament has been successfully received and is currently under review.\n\nYou will receive another email once a decision has been made."
    )
    
    return application

@router.get("/export", response_class=Response)
async def export_applications_csv(
    current_user: Annotated[User, Depends(allow_review_roles)],
    service: ApplicationService = Depends(get_application_service),
    status: str | None = Query(None, description="Filter by status"),
    category: str | None = Query(None, description="Filter by category"),
    organization_id: uuid.UUID | None = Query(None, description="Filter by organization ID"),
):
    """Exports all filtered applications as a downloadable CSV file."""
    items, _ = await service.get_applications(
        status=status, category=category, organization_id=organization_id, limit=None
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if items:
        headers = list(items[0].keys())
        writer.writerow(headers)
        for item in items:
            writer.writerow([item.get(h, "") for h in headers])
    else:
        writer.writerow(["No applications found matching criteria."])
        
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="applications_export.csv"'
    return response

@router.get("/track/status", response_model=ApplicationTrackResponse, summary="Public Status Tracker")
async def track_application_status(
    email: str | None = Query(None, description="Registered email address"),
    reference_number: str | None = Query(None, description="Application reference number (UUID)"),
    service: ApplicationService = Depends(get_application_service)
):
    """Allows a user to track their application status using their email or UUID on the public portal."""
    return await service.track_application_status(email=email, reference_number=reference_number)

@router.get("/", response_model=ApplicationListResponse, summary="List Applications (Paginated)")
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
    """
    Retrieves a paginated list of applications for the Admin Dashboard Data Tables.
    
    **Frontend Implementation Notes:**
    - Security is handled automatically: Applicants only see their own, Org Admins see their team's, Admins see all.
    - Pass `page` and `limit` query parameters to handle pagination UI.
    - Pass `status` (e.g., `?status=pending`) or `category` to filter the table.
    """
    skip = (page - 1) * limit
    
    # Resolve user filter constraint: admins see all, applicants see their own
    if current_user.role in ["admin", "loc_admin", "officer"]:
        user_id_filter = None
    elif current_user.role == "org_admin":
        user_id_filter = None
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Org Admin account is not associated with an organization.")
        organization_id = current_user.organization_id
    else:
        user_id_filter = current_user.id
    
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
    application = await service.get_application_by_id(application_id)
    
    # SECURITY: Prevent IDOR. Enforce strict ownership boundaries.
    if current_user.role == "applicant" and application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this application.")
    if current_user.role == "org_admin" and application.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this application.")
        
    return application

@router.put("/batch/review", response_model=List[ApplicationRead])
async def review_applications_batch(
    review_in: ApplicationBatchReview,
    current_user: Annotated[User, Depends(allow_review_roles)],
    service: ApplicationService = Depends(get_application_service)
):
    """Bulk approve or reject multiple applications simultaneously."""
    applications = await service.review_applications_batch(current_user.id, review_in)
    
    # Automatically trigger background emails for all approved applications
    if review_in.status.lower() == "approved":
        for app in applications:
            send_email_notification.delay(
                recipient_email=app.email,
                subject="Your Accreditation Application is Approved!",
                body=f"Congratulations {app.first_name}, your application for category {app.category} has been approved and you are now an official Participant!"
            )
    return applications

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
        send_email_notification.delay(
            recipient_email=application.email,
            subject="Your Accreditation Application is Approved!",
            body=f"Congratulations {application.first_name}, your application for category {application.category} has been approved and you are now an official Participant!"
        )
            
    return application

@router.patch("/documents/{document_id}/review", response_model=DocumentRead)
async def review_document(
    document_id: uuid.UUID,
    review_in: DocumentReview,
    current_user: Annotated[User, Depends(allow_review_roles)],
    service: ApplicationService = Depends(get_application_service)
):
    document = await service.review_document(document_id, current_user.id, review_in)
    
    if review_in.status.lower() == "rejected":
        application = await service.get_application_by_id(document.application_id)
        if application:
            send_email_notification.delay(
                recipient_email=application.email,
                subject=f"Action Required: Update your ACCRA 2026 Document ({document.document_type.upper()})",
                body=f"Hello {application.first_name},\n\nThere is an issue with the '{document.document_type}' document you uploaded for your accreditation application.\n\nReason: {review_in.rejection_reason}\n\nPlease log in to the portal to re-upload a valid document so your application can proceed."
            )
    return document