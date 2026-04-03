import uuid
from pydantic import BaseModel

class ScanRequest(BaseModel):
    participant_id: uuid.UUID
    zone_id: uuid.UUID

class ScanResponse(BaseModel):
    access: str
    reason: str | None = None
    role: str | None = None