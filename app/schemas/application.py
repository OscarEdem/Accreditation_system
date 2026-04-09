import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
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

class ApplicationCategory(str, Enum):
    athlete = "Athlete"
    team_official = "Team Official"
    technical_competition_official = "Technical and Competition Officials"
    loc_staff = "LOC Staff"
    volunteer = "Volunteer"
    media = "Media"
    security = "Security"
    vip_sponsor = "VIP and Sponsors"
    
    # --- NEW CAA & WORLD ATHLETICS STANDARDS ---
    category_a = "Athletes & Team Officials"
    category_t = "Technical & Competition Officials"
    category_l = "LOC & Workforce"
    category_m = "Media & Broadcast"
    category_v = "VIPs & Dignitaries"
    category_s = "Service Providers"

class ApplicationBase(BaseModel):
    tournament_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID | None = None  # Will be auto-filled by the backend as "Submitted By"
    first_name: str
    last_name: str
    email: str
    organization_id: Optional[uuid.UUID] = None
    category: ApplicationCategory
    photo_url: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[GenderEnum] = None
    country: str
    sporting_disciplines: Optional[List[str]] = []

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