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

    # == 1. Team Officials ==
    chef_de_mission_cdm = "Chef de Mission (CDM)"
    team_manager = "Team Manager"
    team_administrator = "Team Administrator"
    coach = "Coach"
    assistant_coach = "Assistant Coach"
    team_doctor = "Team Doctor"
    physiotherapist = "Physiotherapist"
    media_attache = "Media Attaché"
    tic_coordinator = "TIC Coordinator"
    team_support_staff = "Team Support Staff"

    # == 2. Technical Officials ==
    chief_judge = "Chief Judge"
    track_judge = "Track Judge"
    race_walk_judge = "Walking Judge"
    jury = "Jury of Appeal"
    chief_referee = "Chief Referee"
    referee = "Referee"
    starter = "Starter"
    recall_starter = "Recall Starter"
    photo_finish_referee = "Photo Finish Referee"
    wind_gauge_operator = "Wind Gauge Operator"
    technical_manager = "Technical Manager"
    field_judge_high_jump = "Field Judge – High Jump"
    field_judge_pole_vault = "Field Judge – Pole Vault"
    field_judge_long_triple_jump = "Field Judge – Long/Triple Jump"
    field_judge_throwing_events = "Field Judge – Throwing Events"
    doping_control_officer = "Doping Control Officer"
    anti_doping_chaperone = "Anti-Doping Chaperone"
    medical_officer = "Medical Officer"
    timekeeper = "Timekeeper"
    records_results_officer = "Records & Results Officer"
    technical_information_officer = "Technical Information Officer"
    competition_secretary = "Competition Secretary"
    event_coordinator = "Event Coordinator"
    announcer = "Announcer"

    # == 3. LOC Staff ==
    loc_chairperson = "LOC Chairperson"
    loc_member = "LOC Member"
    director_general = "Director General"
    event_director = "Event Director"
    loc_event_coordinator = "Event Coordinator" # duplicate value aliased
    operations_manager = "Operations Manager"
    competition_director = "Competition Director"
    competition_coordinator = "Competition Coordinator"
    venue_manager = "Venue Manager"
    finance_officer = "Finance Officer"
    legal_officer = "Legal Officer"
    marketing_communications_officer = "Marketing & Communications Officer"
    logistics_officer = "Logistics Officer"
    administrative_officer = "Administrative Officer"
    accreditation_officer = "Accreditation Officer"
    protocol_officer = "Protocol Officer"
    transport_coordinator = "Transport Coordinator"
    volunteer_coordinator = "Volunteer Coordinator"
    broadcast_coordinator = "Broadcast Coordinator"
    it_technology_officer = "IT/Technology Officer"
    security_coordinator = "Security Coordinator"
    medical_coordinator = "Medical Coordinator"
    accreditation_manager = "Accreditation Manager"
    accreditation_staff = "Accreditation Staff"

    # == 4. Media ==
    director_producer = "Director/Producer"
    editor = "Editor"
    rights_holder_media = "Rights Holder Media"
    production_crew = "Production Crew"
    technical_broadcast_staff = "Technical Broadcast Staff"
    broadcast_journalist_tv = "Broadcast Journalist – Television"
    broadcast_journalist_radio = "Broadcast Journalist – Radio"
    print_online_reporter = "Print/Online Reporter"
    news_agency_correspondence = "New Agency Correspondence"
    photographer = "Photographer"
    videographer_camera_operator = "Videographer/Camera Operator"
    sound_engineer = "Sound Engineer"
    commentator_analyst = "Commentator/Analyst"
    social_media_digital_reporter = "Social Media/Digital Reporter"

    # == 5. VIP/Guests ==
    head_of_state = "Head of State"
    government_official = "Government Official"
    ambassador_diplomat = "Ambassador/Diplomat"
    world_athletics_president = "World Athletics President"
    world_athletics_senior_vp = "World Athletics Senior Vice President"
    world_athletics_vp = "World Athletics Vice President"
    world_athletics_council_member = "World Athletics Council Member"
    world_athletics_family_member = "World Athletics Family Member"
    caa_president = "CAA President"
    caa_ceo = "CAA CEO"
    caa_council_member = "CAA Council Member"
    naf_president = "National Athletics Federation President"
    naf_vp = "National Athletics Federation Vice President"
    naf_ceo = "National Athletics Federation CEO"
    naf_member = "National Athletics Federation Member"
    noc_president = "NOC President"
    noc_secretary_general = "NOC Secretary General"
    noc_member = "NOC Member"
    guest_of_honor = "Guest of Honor"
    invited_guest = "Invited Guest"
    international_observer = "International Observer"
    mosr_chief_director = "MOSR Chief Director"
    mosr_technical_advisor = "MOSR Technical Advisor"
    mosr_director = "MOSR Director"
    mosr_staff = "MOSR Staff"
    nsa_board_chairperson = "NSA Board Chairperson"
    nsa_director = "NSA Director General"
    nsa_deputy_directors = "NSA Deputy Director General"
    nsa_members = "NSA Board Member"
    general_coordinator = "General Coordinator"
    technical_coordinator = "Technical Coordinator"
    technical_delegate = "Technical Delegate"
    deputy_technical_delegate = "Deputy Technical Delegate"
    antidoping_control_delegate = "Antidoping Control Delegate"
    organizational_delegate = "Organizational Delegate"
    protocol_delegate = "Protocol Delegate"
    tv_production_media_delegate = "TV Production & Media Delegate"
    caa_headquarters_staff = "CAA Headquarters Staff"
    accompanying_guest = "Accompanying Guest"

    # == 6. Service Staff ==
    access_control_officer = "Access Control Officer"
    security_supervisor = "Security Supervisor"
    security_officer = "Security Officer"
    doctor = "Doctor"
    nurse_medical_officer = "Nurse/Medical Officer"
    svc_physiotherapist = "Physiotherapist" # duplicate aliased
    paramedics_first_aider = "Paramedics/First Aider"
    anti_doping_officer = "Anti-Doping Officer"
    svc_anti_doping_chaperone = "Anti-Doping Chaperone" # duplicate aliased
    fleet_supervisor = "Fleet Supervisor"
    driver_chauffeur = "Driver/Chauffeur"
    catering_supervisor = "Catering Supervisor"
    catering_staff = "Catering Staff"
    facilities_supervisor = "Facilities Supervisor"
    facilities_cleaning_staff = "Facilities/Cleaning Staff"
    electrician_technician = "Electrician/Technician"
    it_support_technician = "IT Support Technician"
    it_support_staff = "IT Support Staff"
    equipment_logistics_handler = "Equipment/Logistics Handler"
    event_manager = "Event Manager"
    ceremonies = "Ceremonies"
    artist = "Artist"
    event_crew = "Event Crew"
    performers = "Performers"
    vendor = "Vendor"
    official_content_crew = "Official Content Crew"

    # == 7. Volunteers ==
    technical_competition_support_volunteer = "Technical and Competition Support Volunteer"
    media_communications_volunteer = "Media and Communications Volunteer"
    protocol_vip_volunteer = "Protocol and VIP Volunteer"
    transport_volunteer_role = "Transport Volunteer"
    medical_anti_doping_volunteer = "Medical and Anti-Doping Volunteer"
    accreditation_info_volunteer = "Accreditation and Information Volunteer"
    language_volunteer = "Language Volunteer"
    team_attache_volunteer = "Team Attaché Volunteer"
    accommodation_volunteer = "Accommodation Volunteer"
    events_ceremonies_volunteer = "Events and Ceremonies Volunteer"

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