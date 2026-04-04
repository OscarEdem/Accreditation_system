import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict

class ParticipantBase(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: str

class ParticipantCreate(ParticipantBase):
    pass

class ParticipantRead(ParticipantBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ParticipantListResponse(BaseModel):
    total: int
    items: List[ParticipantRead]