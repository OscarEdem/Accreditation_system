import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class OrganizationBase(BaseModel):
    name: str
    type: str
    country: Optional[str] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    country: Optional[str] = None

class OrganizationRead(OrganizationBase):
    id: uuid.UUID
    created_at: datetime
    allowed_categories: Optional[List[str]] = []
    
    model_config = ConfigDict(from_attributes=True)

class OrganizationListResponse(BaseModel):
    total: int
    items: List[OrganizationRead]