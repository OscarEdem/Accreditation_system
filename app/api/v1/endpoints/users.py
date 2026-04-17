import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, or_
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.user import UserRead, UserUpdateRole, UserUpdateStatus, UserRole, UserListResponse
from app.services.user import UserService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.config.settings import settings
from app.core.constants import SEEDED_ORGANIZATIONS
from app.models.organization import Organization
from app.core.constants import ORG_TYPE_ALLOWED_CATEGORIES
from app.models.category import Category
import logging

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])
allow_read_users = RoleChecker(["admin", "loc_admin", "org_admin", "officer"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

@router.get("/", response_model=UserListResponse, summary="List Users (Paginated)")
async def get_users(
    current_user: Annotated[User, Depends(allow_read_users)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by name or email")
):
    """
    Fetch a paginated list of all users.
    
    **Frontend Implementation Notes:**
    - Used for the Admin Dashboard User Management table.
    - Org Admins will only see users belonging to their own organization. Super Admins see everyone.
    """
    skip = (page - 1) * limit
    
    # Base condition: Hide the root Super Admin account from the list
    base_conditions = [User.email != "admin@example.com"]

    # Org Admins should only see users from their own organization
    if str(current_user.role) == "org_admin":
        if not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Org Admin account is not associated with an organization.")
        base_conditions.append(User.organization_id == current_user.organization_id)
    
    if search:
        search_term = f"%{search}%"
        base_conditions.append(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    count_stmt = select(func.count()).select_from(User).where(*base_conditions)
    total = await db.scalar(count_stmt)
    
    stmt = select(User).where(*base_conditions).order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return {"total": total, "items": users}

@router.patch("/{user_id}/role", response_model=UserRead, summary="Change User Role")
async def update_user_role(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    role: UserRole = Form(...),
    organization_id: str | None = Form(None)
):
    """
    Elevate or downgrade a user's privileges.
    
    **Frontend Implementation Notes:**
    - If assigning `org_admin`, you **must** also pass an `organization_id` in the form data.
    """
    # Safely handle empty strings from HTML forms
    org_uuid = None
    if organization_id and organization_id.strip():
        try:
            org_uuid = uuid.UUID(organization_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization_id format")
            
    # Enforce Organization requirements based on Role
    if role in [UserRole.org_admin, UserRole.applicant]:
        if not org_uuid:
            raise HTTPException(status_code=400, detail=f"An Organization must be selected for the {role.value} role.")
    else:
        org_uuid = None  # Ensure system admins/staff don't get tied to a participant organization
            
    return await service.update_user_role(user_id, role, org_uuid)

@router.patch("/{user_id}/status", response_model=UserRead, summary="Toggle Account Status")
async def update_user_status(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis),
    is_active: bool = Form(...)
):
    """
    Activates or Deactivates a user account.
    If `is_active` is set to false, their active Redis session is instantly revoked, forcing them out of the system.
    """
    user = await service.update_user_status(user_id, is_active)
    if not is_active:
        await redis.set(f"active_session:{user_id}", "revoked", ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return user

@router.delete("/clear-database", summary="DANGEROUS: Wipe Test Data")
async def clear_database(
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db)
):
    """
    DANGEROUS: Clears all tables in the database except for admin users.
    """
    tables_to_clear = [
        "applications", # Will cascade to participants, badges, documents, etc.
        "zones",        # Will cascade to zone_access
        "audit_logs",   # Contains only transactional data
        "scan_logs",    # Contains only transactional data
        "teams",        # Contains only transactional data
    ]
    
    # 1. Truncate all transactional tables (removes foreign key constraints on users and orgs)
    truncate_query = f"TRUNCATE {', '.join(tables_to_clear)} CASCADE;"
    await db.execute(text(truncate_query))
    
    # 2. Delete all users except admins and loc_admins
    await db.execute(text("DELETE FROM users WHERE role NOT IN ('admin', 'loc_admin')"))
    
    # 3. Delete all organizations except the officially seeded ones
    # Use parameterized query for safety and clarity
    await db.execute(text("DELETE FROM organizations WHERE name NOT IN :seeded_orgs"), {"seeded_orgs": tuple(SEEDED_ORGANIZATIONS)})
    await db.commit()
    
    return {"message": "Database wiped successfully. Only admin users remain."}

@router.get("/debug/user-categories", tags=["Debugging"], summary="Diagnose Category Issues for a User")
async def debug_user_categories(
    email: str,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db)
):
    """
    A temporary debugging endpoint for admins to diagnose why a user 
    might not be seeing the correct accreditation categories.
    """
    user_to_debug = await db.scalar(select(User).where(User.email == email))
    if not user_to_debug:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found.")

    org_name = None
    org_type = None
    is_key_in_constants = False
    categories_from_constants = "N/A"
    final_allowed_categories = []

    # Get all categories for context
    all_system_categories = list((await db.scalars(select(Category.name))).all())

    # Logic for system-level admins
    if user_to_debug.role in [UserRole.admin, UserRole.loc_admin, UserRole.officer]:
        final_allowed_categories = all_system_categories
    # Logic for org-level users
    elif user_to_debug.organization_id:
        looked_up_org = await db.get(Organization, user_to_debug.organization_id)
        if looked_up_org:
            org_name = looked_up_org.name
            org_type = looked_up_org.type
            is_key_in_constants = org_type in ORG_TYPE_ALLOWED_CATEGORIES
            categories_from_constants = ORG_TYPE_ALLOWED_CATEGORIES.get(org_type, "NOT FOUND in constants.py")
            if isinstance(categories_from_constants, list):
                final_allowed_categories = categories_from_constants

    return {
        "message": "Debug information for user's allowed categories. Check for mismatches or NULL values.",
        "user_email": user_to_debug.email,
        "user_role": user_to_debug.role,
        "logic_path_taken": "System Admin (gets all categories)" if user_to_debug.role in [UserRole.admin, UserRole.loc_admin, UserRole.officer] else "Organization-based",
        "user_organization_id": str(user_to_debug.organization_id) if user_to_debug.organization_id else None,
        "organization_name_from_db": org_name,
        "organization_type_from_db": org_type,
        "org_type_matches_constants_key": is_key_in_constants,
        "categories_found_in_constants_py": categories_from_constants,
        "final_categories_returned_to_frontend": final_allowed_categories,
        "all_categories_in_system": all_system_categories
    }