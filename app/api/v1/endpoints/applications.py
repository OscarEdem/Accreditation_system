import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.services.application import ApplicationService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)

@router.post("/", response_model=ApplicationRead, status_code=201)
async def create_application(
    application_in: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service)
):
    return await service.create_application(application_in)

@router.get("/", response_model=List[ApplicationRead])
async def get_applications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service)
):
    return await service.get_applications()

@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: ApplicationService = Depends(get_application_service)
):
    return await service.get_application_by_id(application_id)