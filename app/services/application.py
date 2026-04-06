import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationReview
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.schemas.document import DocumentReview
from app.models.participant import Participant
from app.models.badge import Badge

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

        app_data = application_in.model_dump(exclude={"documents"})
        application = Application(**app_data)
        self.session.add(application)
        await self.session.flush()

        if application_in.documents:
            docs = [Document(**doc.model_dump(), application_id=application.id) for doc in application_in.documents]
            self.session.add_all(docs)
            
        await self.session.commit()
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id == application.id)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_applications(
        self, 
        user_id: uuid.UUID | None = None, 
        status: str | None = None, 
        category: str | None = None,
        organization_id: uuid.UUID | None = None,
        skip: int = 0, 
        limit: int | None = 100,
        sort_desc: bool = True
    ) -> tuple[list[dict], int]:
        count_stmt = select(func.count(Application.id))
        stmt = (
            select(Application, User.first_name, User.last_name)
            .options(selectinload(Application.documents))
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

        stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
            
        result = await self.session.execute(stmt)
        
        applications = []
        for app, first_name, last_name in result.all():
            app_dict = {c.name: getattr(app, c.name) for c in app.__table__.columns}
            app_dict["submitter_name"] = f"{first_name} {last_name}"
            app_dict["documents"] = app.documents
            applications.append(app_dict)
        return applications, total

    async def get_application_by_id(self, application_id: uuid.UUID) -> Application:
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id == application_id)
        application = (await self.session.execute(stmt)).scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        return application

    async def track_application_status(self, email: str | None = None, reference_number: str | None = None) -> dict:
        if not email and not reference_number:
            raise HTTPException(status_code=400, detail="Please provide an email or reference number.")
            
        stmt = (
            select(
                Application.id,
                Application.first_name,
                Application.last_name,
                Application.status,
                Application.category,
                Badge.status.label("badge_status")
            )
            .outerjoin(Participant, Participant.application_id == Application.id)
            .outerjoin(Badge, Badge.participant_id == Participant.id)
        )
        
        if reference_number:
            try:
                app_id = uuid.UUID(reference_number)
                stmt = stmt.where(Application.id == app_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid reference number format.")
        else:
            stmt = stmt.where(Application.email == email)
            
        # Order by newest first in case they have multiple historical applications
        stmt = stmt.order_by(Application.submitted_at.desc()).limit(1)
        
        row = (await self.session.execute(stmt)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Application not found. Please check your details.")
            
        # Return a safe dictionary mapping to the ApplicationTrackResponse schema
        return {"reference_number": row.id, "first_name": row.first_name, "last_name": row.last_name, "status": row.status, "category": row.category, "badge_status": row.badge_status or "Pending Generation"}

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

    async def review_document(self, document_id: uuid.UUID, reviewer_id: uuid.UUID, review_data: DocumentReview) -> Document:
        document = await self.session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document.status = review_data.status
        document.rejection_reason = review_data.rejection_reason
        
        audit_log = AuditLog(
            entity_type="document",
            entity_id=document.id,
            action="document_status_change",
            new_value=review_data.status,
            user_id=reviewer_id
        )
        self.session.add(audit_log)
        
        await self.session.commit()
        await self.session.refresh(document)
        return document