from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel

class Venue(BaseModel):
    __tablename__ = "venues"
    
    name: Mapped[str] = mapped_column(String, index=True)
    address: Mapped[str] = mapped_column(String)
    capacity: Mapped[int] = mapped_column(Integer)
    contact_email: Mapped[str] = mapped_column(String)