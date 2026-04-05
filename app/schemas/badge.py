import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict

class BadgeStatus(str, Enum):
    active = "active"
    revoked = "revoked"
    printed = "printed"

class BadgeBase(BaseModel):
    participant_id: uuid.UUID
    serial_number: str
    status: BadgeStatus = BadgeStatus.active

class BadgeUpdate(BaseModel):
    status: BadgeStatus

class BadgeRead(BadgeBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)