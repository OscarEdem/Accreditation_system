import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ParticipantRole(str, Enum):
    # Athlete / Team Official Roles
    athlete = "Athlete"
    team_official = "Team Official"
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
    technical_volunteer = "Technical Volunteers"
    media_volunteer = "Media Volunteers"
    protocol_volunteer = "Protocol Volunteers"
    transport_volunteer = "Transport Volunteers"
    medical_anti_doping_volunteer = "Medical and Anti-Doping Volunteers"
    security_volunteer = "Security Volunteers"
    accreditation_information_volunteer = "Accreditation and Information Volunteers"
    
    # Other Generic Categories
    media = "Media"
    security = "Security"
    
    # --- NEW CAA & WORLD ATHLETICS STANDARDS ---
    # Generic Categories (Fallbacks)
    category_a = "Athletes & Team Officials"
    category_t = "Technical & Competition Officials"
    category_l = "LOC & Workforce"
    category_m = "Media & Broadcast"
    category_v = "VIPs & Dignitaries"
    category_s = "Service Providers"

    # A - Athletes & Team Officials
    athletes = "Athletes"
    coaches = "Coaches"
    team_managers = "Team Managers"
    medical_personnel = "Medical Personnel"
    nf_official = "NF Officials"

    # T - Technical & Competition Officials
    referee_judge = "Referees & Judges"
    starter = "Starters"
    timekeeper = "Timekeepers"
    tech_delegate = "Tech Delegates"

    # L - LOC & Workforce
    loc_member = "LOC Members"
    accreditation_staff = "Accreditation Staff"
    volunteers = "Volunteers"
    protocol_officer = "Protocol Officers"

    # M - Media & Broadcast
    written_press = "Written Press"
    photographer = "Photographers"
    host_broadcaster = "Host Broadcaster"
    rights_holder = "Rights Holders"

    # V - VIPs & Dignitaries
    government_official = "Government Officials"
    caa_council = "CAA Council"
    sponsor = "Sponsors"
    invited_guest = "Invited Guests"

    # S - Service Providers
    security_agency = "Security Agencies"
    medical_service = "Medical Services"
    it_timing = "IT & Timing"
    venue_management = "Venue Management"

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