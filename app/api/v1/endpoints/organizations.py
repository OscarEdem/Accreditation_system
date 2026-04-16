import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query, Form, status, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationListResponse, OrganizationUpdate
from app.services.organization import OrganizationService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)

@router.post("/", response_model=OrganizationRead, status_code=201, summary="Create Organization")
async def create_organization(
    current_user: Annotated[User, Depends(allow_admin)],
    service: OrganizationService = Depends(get_organization_service),
    name: str = Form(...),
    type: str = Form(...),
    country: str | None = Form(None)
):
    """Admin endpoint to register a new organization/team in the system."""
    org_in = OrganizationCreate(name=name, type=type, country=country)
    return await service.create_organization(org_in)

@router.get("/", response_model=OrganizationListResponse, summary="List Organizations (Paginated)")
async def get_organizations(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by organization name"),
    type: str | None = Query(None, description="Filter by organization type")
):
    """
    Fetch a list of all organizations. 
    
    **Frontend Implementation Notes:**
    - Use this to populate the "Select Organization" dropdown in the application form.
    - Each organization returned includes an `allowed_categories` array. You can use this to dynamically filter the Categories dropdown!
    """
    skip = (page - 1) * limit
    items, total = await service.get_organizations(skip=skip, limit=limit, search=search, org_type=type)
    return {"total": total, "items": items}

@router.get("/{org_id}", response_model=OrganizationRead, summary="Get Single Organization")
async def get_organization(
    org_id: uuid.UUID,
    service: Organiza
    """Fetch details of a specific organization by its UUID."""
    return await service.get_organization_by_id(org_id)

@router.patch("/{org_id}", response_model=OrganizationRead, summary="Update Organization")
async def update_organization(
    org_id: uuid.UUID,
    update_in: OrganizationUpdate,
    current_user: Annotated[User, Depends(allow_admin)],
    service: OrganizationService = Depends(get_organization_service)
):
    """Update an organization's details (e.g., fixing a typo in the team name)."""
    return await service.update_organization(org_id, update_in)

@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Organization")
async def delete_organization(
    org_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: OrganizationService = Depends(get_organization_service)
):
    await service.delete_organization(org_id)