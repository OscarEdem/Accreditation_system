import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class OrganizationBase(BaseModel):
    name: str
    type: str
    country: Optional[str] = None
    allowed_categories: Optional[List[str]] = []

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    country: Optional[str] = None
    allowed_categories: Optional[List[str]] = None

class OrganizationRead(OrganizationBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class OrganizationListResponse(BaseModel):
    total: int
    items: List[OrganizationRead]