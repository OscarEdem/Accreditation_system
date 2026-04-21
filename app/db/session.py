import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria, ORMExecuteState
from sqlalchemy import select
from app.config.settings import settings
from app.core.tenant import tenant_user_id, tenant_role, tenant_org_id
from app.models.application import Application
from app.models.participant import Participant

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_scoping(execute_state: ORMExecuteState):
    """
    Global ORM event that intercepts every query and automatically appends 
    tenant-scoping rules (IDOR protection at the database repository layer).
    """
    if execute_state.execution_options.get("ignore_tenant_scoping", False):
        return

    if execute_state.is_select and not execute_state.is_column_load:
        role = tenant_role.get()
        
        # Privileged roles bypass scoping
        if role in ["admin", "loc_admin", "officer", "scanner", None]:
            return
            
        user_id_str = tenant_user_id.get()
        org_id_str = tenant_org_id.get()
        
        # Comprehensive tenant scoping for all sensitive tables
        from app.models.badge import Badge
        from app.models.scan_log import ScanLog
        from app.models.audit_log import AuditLog
        from app.models.document import Document
        if role == "applicant" and user_id_str:
            user_uuid = uuid.UUID(user_id_str)
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(Application, Application.user_id == user_uuid),
                with_loader_criteria(Participant, Participant.application.has(Application.user_id == user_uuid)),
                with_loader_criteria(Badge, Badge.participant.has(Participant.application.has(Application.user_id == user_uuid))),
                with_loader_criteria(ScanLog, ScanLog.participant.has(Participant.application.has(Application.user_id == user_uuid))),
                with_loader_criteria(Document, Document.application.has(Application.user_id == user_uuid)),
                with_loader_criteria(AuditLog, AuditLog.entity_id.in_(
                    select(Application.id).where(Application.user_id == user_uuid)
                ))
            )
        elif role == "org_admin" and org_id_str:
            org_uuid = uuid.UUID(org_id_str)
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(Application, Application.organization_id == org_uuid),
                with_loader_criteria(Participant, Participant.organization_id == org_uuid),
                with_loader_criteria(Badge, Badge.participant.has(Participant.organization_id == org_uuid)),
                with_loader_criteria(ScanLog, ScanLog.participant.has(Participant.organization_id == org_uuid)),
                with_loader_criteria(Document, Document.application.has(Application.organization_id == org_uuid)),
                with_loader_criteria(AuditLog, AuditLog.entity_id.in_(
                    select(Application.id).where(Application.organization_id == org_uuid)
                ))
            )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session