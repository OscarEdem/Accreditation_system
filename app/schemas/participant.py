import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ParticipantRole(str, Enum):
    # == Generic Roles (Mirrors ApplicationCategory) ==
    # These are used as fallbacks when a specific role isn't assigned.
    athlete = "Athlete"
    coaches = "Coaches"
    team_officials = "Team Officials"
    technical_officials = "Technical Officials"
    medical_staff = "Medical Staff"
    media = "Media"
    vip_guests = "VIP/Guests"
    loc_staff = "LOC Staff"
    volunteer = "Volunteer"
    security = "Security"
    transport = "Transport"
    service_staff = "Service Staff"

    # == Specific Granular Roles ==
    # --- Athlete / Team Official Roles ---
    chef_de_mission = "Chef De Mission (CDM)"
    media_attache = "Media Attache"
    team_doctor = "Team Doctor"
    general_manager = "General Manager"
    physiotherapist = "Physiotherapist"
    team_administrator = "Team Administrator"
    
    # --- Technical and Competition Officials ---
    chief_judge = "Chief Judge"
    event_referee = "Event Referee"
    competition_director = "Competition Director"
    anti_doping_official = "Anti-Doping Official"
    
    # --- LOC Staff and Volunteers ---
    technical_volunteers = "Technical Volunteers"
    media_volunteers = "Media Volunteers"
    protocol_volunteers = "Protocol Volunteers"
    transport_volunteers = "Transport Volunteers"
    medical_and_anti_doping_volunteers = "Medical and Anti-Doping Volunteers"
    security_volunteers = "Security Volunteers"
    accreditation_and_information_volunteers = "Accreditation and Information Volunteers"
    
    # --- Other Specific Roles ---
    transport_staff = "Transport Staff"

class ParticipantBase(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: ParticipantRole
    organization_id: Optional[uuid.UUID] = None
    sporting_disciplines: Optional[List[str]] = []

class ParticipantCreate(BaseModel):
    application_id: uuid.UUID
    tournament_id: uuid.UUID
    role: Optional[ParticipantRole] = None  # Will auto-set based on Application Category if not provided
    organization_id: Optional[uuid.UUID] = None
    sporting_disciplines: Optional[List[str]] = []

class ParticipantRead(ParticipantBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ParticipantListResponse(BaseModel):
    total: int
    items: List[ParticipantRead]