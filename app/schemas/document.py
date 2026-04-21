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
    passport = "Valid Passport"
    nomination_letter = "Appointment/Nomination Letter"
    medical_certificate = "Medical Certificate"
    liability_waiver = "Liability Waiver"
    other = "Other"

from pydantic import field_validator

class DocumentBase(BaseModel):
    document_type: DocumentType
    file_url: str

    @field_validator('file_url')
    @classmethod
    def validate_file_url(cls, v: str) -> str:
        # Only allow HTTPS URLs from the configured S3 bucket
        from urllib.parse import urlparse
        from app.config.settings import settings
        parsed = urlparse(str(v))
        if parsed.scheme != "https":
            raise ValueError("Document URLs must use HTTPS protocol")
        allowed_domains = [
            f"{settings.S3_BUCKET_NAME}.s3.amazonaws.com",
            f"{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com"
        ]
        if parsed.netloc not in allowed_domains:
            raise ValueError(f"Document must be hosted on approved S3 bucket")
        return str(v)

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