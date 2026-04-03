import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ApplicationBase(BaseModel):
    user_id: uuid.UUID
    category: str
    photo_url: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationRead(ApplicationBase):
    id: uuid.UUID
    status: str
    submitted_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)