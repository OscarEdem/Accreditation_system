import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ApplicationBase(BaseModel):
    user_id: uuid.UUID | None = None  # Will be auto-filled by the backend as "Submitted By"
    first_name: str
    last_name: str
    email: str
    organization_id: Optional[uuid.UUID] = None
    category: str
    photo_url: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationReview(BaseModel):
    status: str  # e.g., "approved", "rejected", "pending"
    reviewer_comments: Optional[str] = None

class ApplicationRead(ApplicationBase):
    id: uuid.UUID
    status: str
    submitted_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ApplicationReadWithSubmitter(ApplicationRead):
    submitter_name: str

class ApplicationListResponse(BaseModel):
    total: int
    items: List[ApplicationReadWithSubmitter]