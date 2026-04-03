import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class Media(BaseModel):
    __tablename__ = "media"
    
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    outlet_name: Mapped[str] = mapped_column(String)
    accreditation_type: Mapped[str] = mapped_column(String)