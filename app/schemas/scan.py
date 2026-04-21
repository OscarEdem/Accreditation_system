import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
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
    issued_at: int | None = None

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
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

class ScanLogRead(BaseModel):
    id: uuid.UUID
    participant_id: Optional[uuid.UUID] = None
    zone_id: uuid.UUID
    scanner_id: uuid.UUID
    access_granted: bool
    reason: Optional[str] = None
    direction: str
    created_at: datetime
    participant_name: str = "Unknown / Forged"
    zone_name: str
    scanner_name: str

class ScanLogListResponse(BaseModel):
    total: int
    items: List[ScanLogRead]