import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.db.base import BaseModel

class Participant(BaseModel):
    __tablename__ = "participants"

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    tournament_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tournaments.id"))
    role: Mapped[str] = mapped_column(String)
    
    sporting_disciplines: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)

    # Reverse relationships to satisfy the back_populates in Organization and Category models
    organization = relationship("Organization", back_populates="participants")
    category = relationship("Category", back_populates="participants")
    application = relationship("Application")