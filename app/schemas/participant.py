import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ParticipantRole(str, Enum):
    athlete = "athlete"
    team_official = "team_official"
    match_official = "match_official"
    media = "media"
    medical = "medical"
    security = "security"
    vip = "vip"
    staff = "staff"

class ParticipantBase(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: ParticipantRole

class ParticipantCreate(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: Optional[ParticipantRole] = None  # Will auto-set based on Application Category if not provided

class ParticipantRead(ParticipantBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ParticipantListResponse(BaseModel):
    total: int
    items: List[ParticipantRead]