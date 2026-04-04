import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class TournamentBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    venue_id: uuid.UUID
    description: Optional[str] = None

class TournamentCreate(TournamentBase):
    pass

class TournamentRead(TournamentBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)