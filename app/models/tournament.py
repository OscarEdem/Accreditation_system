import uuid
from datetime import date
from sqlalchemy import String, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel

class Tournament(BaseModel):
    __tablename__ = "tournaments"
    
    name: Mapped[str] = mapped_column(String, index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    host_city: Mapped[str] = mapped_column(String)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"))
    description: Mapped[str | None] = mapped_column(String, nullable=True)