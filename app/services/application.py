import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationReview
from app.models.user import User
from app.models.audit_log import AuditLog

class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_application(self, application_in: ApplicationCreate, bypass_duplicate_check: bool = False) -> Application:
        # Prevent double-submissions for the same user
        if not bypass_duplicate_check:
            stmt = select(Application).where(Application.user_id == application_in.user_id)
            existing = await self.session.execute(stmt)
            if existing.scalars().first():
                raise HTTPException(status_code=400, detail="You have already submitted an application.")

        application = Application(**application_in.model_dump())
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def get_applications(
        self, 
        user_id: uuid.UUID | None = None, 
        status: str | None = None, 
        category: str | None = None,
        organization_id: uuid.UUID | None = None,
        skip: int = 0, 
        limit: int = 100,
        sort_desc: bool = True
    ) -> tuple[list[dict], int]:
        count_stmt = select(func.count(Application.id))
        stmt = (
            select(Application, User.first_name, User.last_name)
            .join(User, Application.user_id == User.id)
        )
        
        if user_id:
            count_stmt = count_stmt.where(Application.user_id == user_id)
            stmt = stmt.where(Application.user_id == user_id)
        if status:
            count_stmt = count_stmt.where(Application.status == status)
            stmt = stmt.where(Application.status == status)
        if category:
            count_stmt = count_stmt.where(Application.category == category)
            stmt = stmt.where(Application.category == category)
        if organization_id:
            count_stmt = count_stmt.where(Application.organization_id == organization_id)
            stmt = stmt.where(Application.organization_id == organization_id)
            
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        if sort_desc:
            stmt = stmt.order_by(Application.submitted_at.desc())
        else:
            stmt = stmt.order_by(Application.submitted_at.asc())

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        
        applications = []
        for app, first_name, last_name in result.all():
            app_dict = {c.name: getattr(app, c.name) for c in app.__table__.columns}
            app_dict["submitter_name"] = f"{first_name} {last_name}"
            applications.append(app_dict)
        return applications, total

    async def get_application_by_id(self, application_id: uuid.UUID) -> Application:
        application = await self.session.get(Application, application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        return application

    async def review_application(self, application_id: uuid.UUID, reviewer_id: uuid.UUID, review_data: ApplicationReview) -> Application:
        application = await self.get_application_by_id(application_id)
        
        old_status = application.status
        application.status = review_data.status
        application.reviewer_comments = review_data.reviewer_comments
        application.reviewer_id = reviewer_id
        
        # Generate an Audit Log entry if the status was changed
        if old_status != review_data.status:
            audit_log = AuditLog(
                entity_type="application",
                entity_id=application.id,
                action="status_change",
                old_value=old_status,
                new_value=review_data.status,
                user_id=reviewer_id
            )
            self.session.add(audit_log)
            
        await self.session.commit()
        await self.session.refresh(application)
        return application