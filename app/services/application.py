import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationReview

class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_application(self, application_in: ApplicationCreate) -> Application:
        application = Application(**application_in.model_dump())
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def get_applications(self) -> list[Application]:
        stmt = select(Application)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_application_by_id(self, application_id: uuid.UUID) -> Application:
        application = await self.session.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        return application

    async def review_application(self, application_id: uuid.UUID, reviewer_id: uuid.UUID, review_data: ApplicationReview) -> Application:
        application = await self.get_application_by_id(application_id)
        application.status = review_data.status
        application.reviewer_comments = review_data.reviewer_comments
        application.reviewer_id = reviewer_id
        await self.session.commit()
        await self.session.refresh(application)
        return application