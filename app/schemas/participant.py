import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ParticipantRole(str, Enum):
    # Athlete / Team Official Roles
    athlete = "Athlete"
    vip_guest = "VIP/Guest"
    chef_de_mission = "Chef De Mission (CDM)"
    media_attache = "Media Attache"
    team_doctor = "Team Doctor"
    general_manager = "General Manager"
    physiotherapist = "Physiotherapist"
    coach = "Coach"
    team_administrator = "Team Administrator"
    
    # Technical and Competition Officials
    chief_judge = "Chief Judge"
    event_referee = "Event Referee"
    competition_director = "Competition Director"
    anti_doping_official = "Anti-Doping Official"
    medical_official = "Medical Official"
    
    # LOC Staff and Volunteers
    loc_staff = "LOC Staff"
    volunteer = "Volunteer"
    
    # Other Generic Categories
    media = "Media"
    security = "Security"

class ParticipantBase(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: ParticipantRole

class ParticipantCreate(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: Optional[ParticipantRole] = None  # Will auto-set based on Application Category if not provided

class ParticipantRead(ParticipantBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ParticipantListResponse(BaseModel):
    total: int
    items: List[ParticipantRead]