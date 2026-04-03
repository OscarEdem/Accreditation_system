import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class Zone(BaseModel):
    __tablename__ = "zones"
    
    name: Mapped[str] = mapped_column(String, index=True)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"))
    description: Mapped[str | None] = mapped_column(String, nullable=True)