import uuid
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.user import UserRead, UserUpdateRole, UserUpdateStatus
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
    update_data: UserUpdateRole,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service)
):
    return await service.update_user_role(user_id, update_data.role, update_data.organization_id)

@router.patch("/{user_id}/status", response_model=UserRead)
async def update_user_status(
    user_id: uuid.UUID,
    update_data: UserUpdateStatus,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis)
):
    user = await service.update_user_status(user_id, update_data.is_active)
    if not update_data.is_active:
        await redis.delete(f"active_session:{user_id}")
    return user