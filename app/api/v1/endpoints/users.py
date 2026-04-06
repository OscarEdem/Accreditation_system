import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.user import UserRead, UserUpdateRole, UserUpdateStatus, UserRole
from app.services.user import UserService
from app.api.deps import RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    role: UserRole = Form(...),
    organization_id: str | None = Form(None)
):
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

@router.patch("/{user_id}/status", response_model=UserRead)
async def update_user_status(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis),
    is_active: bool = Form(...)
):
    user = await service.update_user_status(user_id, is_active)
    if not is_active:
        await redis.delete(f"active_session:{user_id}")
    return user

@router.delete("/clear-database")
async def clear_database(
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db)
):
    """
    DANGEROUS: Clears all tables in the database except for the admin@example.com user.
    """
    tables_to_clear = [
        "applications",
        "tournaments",
        "venues",
        "categories",
        "zones",
        "audit_logs",
        "organizations"
    ]
    
    truncate_query = f"TRUNCATE {', '.join(tables_to_clear)} CASCADE;"
    
    await db.execute(text(truncate_query))
    await db.execute(text("DELETE FROM users WHERE email != 'admin@example.com'"))
    await db.commit()
    
    return {"message": "Database wiped successfully. Only admin@example.com remains."}