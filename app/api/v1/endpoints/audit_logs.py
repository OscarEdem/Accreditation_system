from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.audit_log import AuditLogListResponse
from app.services.audit_log import AuditLogService
from app.api.deps import RoleChecker
from app.models.user import User

router = APIRouter()

allow_super_admin = RoleChecker(["admin"])

def get_audit_log_service(db: AsyncSession = Depends(get_db)) -> AuditLogService:
    return AuditLogService(db)

@router.get("/", response_model=AuditLogListResponse)
async def get_audit_logs(
    current_user: Annotated[User, Depends(allow_super_admin)],
    service: AuditLogService = Depends(get_audit_log_service),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    skip = (page - 1) * limit
    items, total = await service.get_audit_logs(skip=skip, limit=limit)
    return {"total": total, "items": items}