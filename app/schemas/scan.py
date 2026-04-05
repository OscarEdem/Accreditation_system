import uuid
from pydantic import BaseModel
from enum import Enum

class ScanDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"

class ScanRequest(BaseModel):
    participant_id: uuid.UUID
    zone_id: uuid.UUID
    serial_number: str
    signature: str
    direction: ScanDirection

class ScanResponse(BaseModel):
    access: str
    reason: str | None = None
    role: str | None = None

class ScanParticipantProfile(BaseModel):
    first_name: str
    last_name: str
    photo_url: str | None = None
    category: str
    role: str
    organization_name: str | None = None
    badge_status: str | None = None