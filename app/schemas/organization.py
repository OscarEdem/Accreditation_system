import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, computed_field
from app.core.constants import ORG_ALLOWED_CATEGORIES

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
    
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def allowed_categories(self) -> List[str]:
        return ORG_ALLOWED_CATEGORIES.get(self.name, [])

class OrganizationListResponse(BaseModel):
    total: int
    items: List[OrganizationRead]