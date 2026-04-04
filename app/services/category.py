import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.category import Category
from app.schemas.category import CategoryCreate

class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_category(self, category_in: CategoryCreate) -> Category:
        category = Category(**category_in.model_dump())
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def get_categories(self) -> list[Category]:
        stmt = select(Category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_category_by_id(self, category_id: uuid.UUID) -> Category:
        category = await self.session.get(Category, category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        return category