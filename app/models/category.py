from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

class Category(BaseModel):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String, index=True)

    participants = relationship("Participant", back_populates="category")