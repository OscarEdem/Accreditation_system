import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate

class OrganizationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_organization(self, org_in: OrganizationCreate) -> Organization:
        org = Organization(**org_in.model_dump())
        self.session.add(org)
        await self.session.commit()
        await self.session.refresh(org)
        return org

    async def get_organizations(self, skip: int = 0, limit: int = 100) -> tuple[list[Organization], int]:
        count_stmt = select(func.count(Organization.id))
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = select(Organization).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_organization_by_id(self, org_id: uuid.UUID) -> Organization:
        org = await self.session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org