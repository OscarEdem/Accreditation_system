import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.category import Category
from app.schemas.category import CategoryCreate
from app.models.user import User
from app.models.organization import Organization
from app.core.constants import ORG_TYPE_ALLOWED_CATEGORIES

class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, category_in: CategoryCreate) -> Category:
        category = Category(**category_in.model_dump())
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def get_categories(self, current_user: User | None = None) -> list[Category]:
        stmt = select(Category)
        
        # Filter based on user's organization type if they are not a system admin
        if current_user and current_user.role not in ["admin", "loc_admin", "officer"]:
            if current_user.organization_id:
                org = await self.session.get(Organization, current_user.organization_id)
                if org:
                    allowed_names = ORG_TYPE_ALLOWED_CATEGORIES.get(org.type, [])
                    if allowed_names:
                        stmt = stmt.where(Category.name.in_(allowed_names))
                    else:
                        return [] # Return empty list if no categories are permitted
            elif current_user.role == "org_admin" and not current_user.organization_id:
                return [] # Data inconsistency fallback
                
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_category_by_id(self, category_id: uuid.UUID) -> Category:
        category = await self.session.get(Category, category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        return category