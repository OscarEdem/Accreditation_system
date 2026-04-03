from fastapi import APIRouter
from app.api.v1.endpoints import participants, applications, auth, upload, scan, badges

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scan.router, prefix="/scan", tags=["Scan"])
api_router.include_router(upload.router, prefix="/upload", tags=["Uploads"])
api_router.include_router(participants.router, prefix="/participants", tags=["Participants"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(badges.router, prefix="/badges", tags=["Badges"])