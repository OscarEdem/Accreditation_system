from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.orm.query import ORMExecuteState
from app.config.settings import settings
from app.core.tenant import tenant_user_id, tenant_role, tenant_org_id
from app.models.application import Application

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_scoping(execute_state: ORMExecuteState):
    """
    Global ORM event that intercepts every query and automatically appends 
    tenant-scoping rules (IDOR protection at the database repository layer).
    """
    if execute_state.is_select and not execute_state.is_column_load:
        role = tenant_role.get()
        
        # Privileged roles bypass scoping
        if role in ["admin", "loc_admin", "officer", "scanner", None]:
            return
            
        user_id = tenant_user_id.get()
        org_id = tenant_org_id.get()
        
        # Transparently scope Application queries safely at the ORM layer
        if role == "applicant" and user_id:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(Application, Application.user_id == user_id)
            )
        elif role == "org_admin" and org_id:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(Application, Application.organization_id == org_id)
            )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session