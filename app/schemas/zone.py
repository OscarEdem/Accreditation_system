import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ZoneBase(BaseModel):
    name: str
    venue_id: uuid.UUID
    description: Optional[str] = None

class ZoneCreate(ZoneBase):
    pass

class ZoneRead(ZoneBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ZoneAccessCreate(BaseModel):
    category_id: uuid.UUID