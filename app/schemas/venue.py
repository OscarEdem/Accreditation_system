import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VenueBase(BaseModel):
    name: str
    address: str
    capacity: int
    contact_email: str

class VenueCreate(VenueBase):
    pass

class VenueRead(VenueBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)