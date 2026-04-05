import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

class DocumentStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class DocumentType(str, Enum):
    passport = "passport"
    national_id = "national_id"
    medical_clearance = "medical_clearance"
    media_credential = "media_credential"
    other = "other"

class DocumentBase(BaseModel):
    document_type: DocumentType
    file_url: str

class DocumentCreate(DocumentBase):
    pass

class DocumentReview(BaseModel):
    status: DocumentStatus
    rejection_reason: Optional[str] = None

class DocumentRead(DocumentBase):
    id: uuid.UUID
    application_id: uuid.UUID
    status: DocumentStatus
    rejection_reason: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)