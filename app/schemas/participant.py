import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.application import ApplicationRead

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
    technical_volunteer = "Technical Volunteer"
    media_volunteer = "Media Volunteer"
    protocol_volunteer = "Protocol Volunteer"
    transport_volunteer = "Transport Volunteer"
    medical_and_anti_doping_volunteer = "Medical and Anti-Doping Volunteer"
    accreditation_and_information_volunteer = "Accreditation and Information Volunteer"
    language_volunteer = "Language Volunteer"
    team_attache_volunteer = "Team Attaché Volunteer"
    accommodation_volunteer = "Accommodation Volunteer"
    security_volunteer = "Security Volunteer"
    
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
    application: Optional[ApplicationRead] = None
    
    model_config = ConfigDict(from_attributes=True)

class ParticipantListResponse(BaseModel):
    total: int
    items: List[ParticipantRead]