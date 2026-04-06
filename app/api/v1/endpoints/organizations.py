import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationListResponse
from app.services.organization import OrganizationService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)

@router.post("/", response_model=OrganizationRead, status_code=201)
async def create_organization(
    current_user: Annotated[User, Depends(allow_admin)],
    service: OrganizationService = Depends(get_organization_service),
    name: str = Form(...)
):
    org_in = OrganizationCreate(name=name)
    return await service.create_organization(org_in)

@router.get("/", response_model=OrganizationListResponse)
async def get_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    service: OrganizationService = Depends(get_organization_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page")
):
    skip = (page - 1) * limit
    items, total = await service.get_organizations(skip=skip, limit=limit)
    return {"total": total, "items": items}

@router.get("/{org_id}", response_model=OrganizationRead)
async def get_organization(
    org_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: OrganizationService = Depends(get_organization_service)
):
    return await service.get_organization_by_id(org_id)