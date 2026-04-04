from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.audit_log import AuditLog

class AuditLogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_audit_logs(self, skip: int = 0, limit: int = 100) -> tuple[list[AuditLog], int]:
        count_stmt = select(func.count(AuditLog.id))
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total