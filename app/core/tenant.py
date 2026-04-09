from contextvars import ContextVar
from typing import Optional

# Context variables to hold the current request's tenant data for database scoping
tenant_user_id: ContextVar[Optional[str]] = ContextVar("tenant_user_id", default=None)
tenant_role: ContextVar[Optional[str]] = ContextVar("tenant_role", default=None)
tenant_org_id: ContextVar[Optional[str]] = ContextVar("tenant_org_id", default=None)