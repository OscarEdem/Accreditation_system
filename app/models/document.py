import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class Document(BaseModel):
    __tablename__ = "documents"

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"), index=True)
    document_type: Mapped[str] = mapped_column(String)  # e.g., passport, medical_clearance
    file_url: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, approved, rejected
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    application = relationship("Application", back_populates="documents")