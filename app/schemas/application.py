import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.document import DocumentCreate, DocumentRead

class GenderEnum(str, Enum):
    male = "MALE"
    female = "FEMALE"
    other = "OTHER"

class ApplicationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    returned = "returned"

class ApplicationCategory(str, Enum): # Updated to reflect the new list
    athlete = "Athlete"
    coaches = "Coaches"
    team_officials = "Team Officials"
    technical_officials = "Technical Officials"
    medical_staff = "Medical Staff"
    media = "Media"
    vip_guests = "VIP/Guests"
    loc_staff = "LOC Staff"
    volunteer = "Volunteer"
    security = "Security"
    transport = "Transport"
    service_staff = "Service Staff"

class ApplicationBase(BaseModel):
    tournament_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID | None = None  # Will be auto-filled by the backend as "Submitted By"
    first_name: str
    last_name: str
    email: str
    phone_number: Optional[str] = None
    passport_number: Optional[str] = None
    specific_role: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    special_requirements: Optional[str] = None
    organization_id: Optional[uuid.UUID] = None
    category: ApplicationCategory
    photo_url: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[GenderEnum] = None
    country: str
    preferred_language: Literal['en', 'fr', 'pt', 'es', 'ar'] = 'en'
    sporting_disciplines: Optional[List[str]] = []

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str) -> str:
        if any(char.isdigit() for char in v):
            raise ValueError("Names cannot contain numbers.")
        return v

class ApplicationCreate(ApplicationBase):
    documents: List[DocumentCreate] = []

class ApplicationReview(BaseModel):
    status: ApplicationStatus
    reviewer_comments: Optional[str] = None
    assigned_role: Optional[str] = None

class ApplicationBatchReview(BaseModel):
    application_ids: List[uuid.UUID]
    status: ApplicationStatus
    reviewer_comments: Optional[str] = None
    assigned_role: Optional[str] = None

class ApplicationRead(ApplicationBase):
    id: uuid.UUID
    tournament_id: uuid.UUID
    status: str
    submitted_at: datetime
    created_at: datetime
    documents: List[DocumentRead] = []
    
    model_config = ConfigDict(from_attributes=True)

class ApplicationReadWithSubmitter(ApplicationRead):
    submitter_name: str

class ApplicationListResponse(BaseModel):
    total: int
    items: List[ApplicationReadWithSubmitter]

class ApplicationTrackResponse(BaseModel):
    reference_number: uuid.UUID
    first_name: str
    last_name: str
    status: str
    category: str
    badge_status: str | None = None