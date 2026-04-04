from pydantic import BaseModel

class DashboardStats(BaseModel):
    total_applications: int
    pending_applications: int
    approved_applications: int
    rejected_applications: int
    total_participants: int
    total_scans: int
    granted_scans: int
    denied_scans: int