import uuid
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class ScanLog(BaseModel):
    __tablename__ = "scan_logs"

    # Nullable participant_id to safely log forgery attempts where the ID might be fake
    participant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("participants.id"), nullable=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id"))
    scanner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    access_granted: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)