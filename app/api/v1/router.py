from fastapi import APIRouter
from app.api.v1.endpoints import participants, applications, auth, upload, scan, badges, venues, tournaments, zones, categories, stats, organizations, users, audit_logs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scan.router, prefix="/scan", tags=["Scan"])
api_router.include_router(upload.router, prefix="/upload", tags=["Uploads"])
api_router.include_router(participants.router, prefix="/participants", tags=["Participants"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(badges.router, prefix="/badges", tags=["Badges"])
api_router.include_router(venues.router, prefix="/venues", tags=["Venues"])
api_router.include_router(tournaments.router, prefix="/tournaments", tags=["Tournaments"])
api_router.include_router(zones.router, prefix="/zones", tags=["Zones"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(stats.router, prefix="/stats", tags=["Dashboards & Stats"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit & Security"])