import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ZoneBase(BaseModel):
    name: str
    venue_id: uuid.UUID
    description: Optional[str] = None
    is_active: bool = True
    code: Optional[str] = None
    color: Optional[str] = None
    require_qr_scan: bool = True

class ZoneCreate(ZoneBase):
    allowed_categories: List[uuid.UUID] = []

class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    venue_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    code: Optional[str] = None
    color: Optional[str] = None
    require_qr_scan: Optional[bool] = None
    allowed_categories: Optional[List[uuid.UUID]] = None

class ZoneRead(ZoneBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ZoneAccessCreate(BaseModel):
    category_id: uuid.UUID

class ZoneMatrixItem(BaseModel):
    zone_id: uuid.UUID
    category_id: uuid.UUID
    
    model_config = ConfigDict(from_attributes=True)

class ZoneAccessToggleResponse(BaseModel):
    granted: bool
    message: str
    zone_id: uuid.UUID
    category_id: uuid.UUID