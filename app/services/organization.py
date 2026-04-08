import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate

class OrganizationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_organization(self, org_in: OrganizationCreate) -> Organization:
        org = Organization(**org_in.model_dump())
        self.session.add(org)
        await self.session.commit()
        await self.session.refresh(org)
        return org

    async def get_organizations(self, skip: int = 0, limit: int = 100, search: str | None = None, org_type: str | None = None) -> tuple[list[Organization], int]:
        count_stmt = select(func.count(Organization.id))
        stmt = select(Organization)
        
        conditions = []
        if search:
            conditions.append(Organization.name.ilike(f"%{search}%"))
        if org_type:
            conditions.append(Organization.type == org_type)
            
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            stmt = stmt.where(*conditions)
            
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = stmt.order_by(Organization.name.asc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_organization_by_id(self, org_id: uuid.UUID) -> Organization:
        org = await self.session.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org

    async def update_organization(self, org_id: uuid.UUID, org_in: OrganizationUpdate) -> Organization:
        org = await self.get_organization_by_id(org_id)
        
        update_data = org_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)
            
        await self.session.commit()
        await self.session.refresh(org)
        return org

    async def delete_organization(self, org_id: uuid.UUID) -> None:
        org = await self.get_organization_by_id(org_id)
        try:
            await self.session.delete(org)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="Cannot delete this organization because it is actively linked to users, applications, or participants.")