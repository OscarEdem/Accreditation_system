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
from app.api.deps import RoleChecker
from app.models.user import User
from app.config.settings import settings

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
    if current_user.role == UserRole.org_admin:
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
        "applications",
        "tournaments",
        "venues",
        "categories",
        "zones",
        "audit_logs",
    ]
    
    # 1. Truncate all transactional tables (removes foreign key constraints on users and orgs)
    truncate_query = f"TRUNCATE {', '.join(tables_to_clear)} CASCADE;"
    await db.execute(text(truncate_query))
    
    # 2. Delete all users except admins and loc_admins
    await db.execute(text("DELETE FROM users WHERE role NOT IN ('admin', 'loc_admin')"))
    
    # 3. Delete all organizations except the officially seeded ones
    SEEDED_ORGS = [
        "Team Algeria", "Team Angola", "Team Benin", "Team Botswana", "Team Burkina Faso",
        "Team Burundi", "Team Cabo Verde", "Team Cameroon", "Team Central African Republic",
        "Team Chad", "Team Comoros", "Team Congo", "Team Congo (DRC)", "Team Côte d'Ivoire",
        "Team Djibouti", "Team Egypt", "Team Equatorial Guinea", "Team Eritrea", "Team Eswatini",
        "Team Ethiopia", "Team Gabon", "Team Gambia", "Team Ghana", "Team Guinea",
        "Team Guinea-Bissau", "Team Kenya", "Team Lesotho", "Team Liberia", "Team Libya",
        "Team Madagascar", "Team Malawi", "Team Mali", "Team Mauritania", "Team Mauritius",
        "Team Morocco", "Team Mozambique", "Team Namibia", "Team Niger", "Team Nigeria",
        "Team Rwanda", "Team São Tomé and Príncipe", "Team Senegal", "Team Seychelles",
        "Team Sierra Leone", "Team Somalia", "Team South Africa", "Team South Sudan",
        "Team Sudan", "Team Tanzania", "Team Togo", "Team Tunisia", "Team Uganda",
        "Team Zambia", "Team Zimbabwe", "LOC Staff", "Media", "Technical Official",
        "Ghana Athletics Association", "Volunteer", "Service Staff", "VIP/Guest",
        "Confederation of African Athletics", "World Athletics"
    ]
    escaped_orgs = [name.replace("'", "''") for name in SEEDED_ORGS]
    org_names_sql = ", ".join([f"'{name}'" for name in escaped_orgs])
    await db.execute(text(f"DELETE FROM organizations WHERE name NOT IN ({org_names_sql})"))
    await db.commit()
    
    return {"message": "Database wiped successfully. Only admin users remain."}