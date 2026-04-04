import uuid
from typing import List, Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.category import CategoryCreate, CategoryRead
from app.services.category import CategoryService
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_category_service(db: AsyncSession = Depends(get_db)) -> CategoryService:
    return CategoryService(db)

@router.post("/", response_model=CategoryRead, status_code=201)
async def create_category(
    category_in: CategoryCreate,
    current_user: Annotated[User, Depends(allow_admin)],
    service: CategoryService = Depends(get_category_service)
):
    return await service.create_category(category_in)

@router.get("/", response_model=List[CategoryRead])
async def get_categories(
    current_user: Annotated[User, Depends(get_current_user)],
    service: CategoryService = Depends(get_category_service)
):
    return await service.get_categories()

@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: CategoryService = Depends(get_category_service)
):
    return await service.get_category_by_id(category_id)