import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class AuditLogRead(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogRead]