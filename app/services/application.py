import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationReview, ApplicationBatchReview, ApplicationRead, ApplicationReadWithSubmitter
from redis.asyncio import Redis
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.schemas.document import DocumentReview
from app.models.participant import Participant
from app.models.badge import Badge

class ApplicationService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None):
        self.session = session
        self.redis = redis

    async def create_application(self, application_in: ApplicationCreate, bypass_duplicate_check: bool = False) -> Application:
        # Prevent double-submissions for the same user
        if not bypass_duplicate_check:
            if application_in.user_id:
                stmt = select(Application).where(Application.user_id == application_in.user_id)
            else:
                stmt = select(Application).where(Application.email == application_in.email)
                
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

    async def create_applications_batch(self, applications_in: list[ApplicationCreate], submitter_id: uuid.UUID | None = None) -> list[Application]:
        apps = []
        for app_in in applications_in:
            app_data = app_in.model_dump(exclude={"documents"})
            if submitter_id and not app_data.get("user_id"):
                app_data["user_id"] = submitter_id
            app = Application(**app_data)
            self.session.add(app)
            apps.append((app, app_in.documents))
            
        await self.session.flush()
        
        all_docs = []
        for app, docs_in in apps:
            if docs_in:
                all_docs.extend([Document(**doc.model_dump(), application_id=app.id) for doc in docs_in])
                
        if all_docs:
            self.session.add_all(all_docs)
            
        await self.session.commit()
        
        app_ids = [app.id for app, _ in apps]
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id.in_(app_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_applications(
        self, 
        user_id: uuid.UUID | None = None, 
        status: str | None = None, 
        category: str | None = None,
        organization_id: uuid.UUID | None = None,
        allowed_categories: list[str] | None = None,
        skip: int = 0, 
        limit: int | None = 100,
        sort_desc: bool = True
    ) -> tuple[list[ApplicationReadWithSubmitter], int]:
        count_stmt = select(func.count(Application.id))
        stmt = (
            select(Application, User.first_name, User.last_name)
            .options(selectinload(Application.documents))
            .outerjoin(User, Application.user_id == User.id)
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
        if organization_id and allowed_categories:
            count_stmt = count_stmt.where(or_(Application.organization_id == organization_id, Application.category.in_(allowed_categories))).execution_options(ignore_tenant_scoping=True)
            stmt = stmt.where(or_(Application.organization_id == organization_id, Application.category.in_(allowed_categories))).execution_options(ignore_tenant_scoping=True)
        elif organization_id:
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
        for app_model, first_name, last_name in result.all():
            # Use Pydantic model for robust serialization, including relationships
            app_read = ApplicationRead.model_validate(app_model)
            
            if first_name and last_name:
                submitter_name = f"{first_name} {last_name}"
            else:
                submitter_name = f"{app_model.first_name} {app_model.last_name} (Self)"
            
            # Create the final response model
            applications.append(
                ApplicationReadWithSubmitter(**app_read.model_dump(), submitter_name=submitter_name)
            )
        return applications, total

    async def resubmit_returned_application(self, application_id: uuid.UUID, application_in: ApplicationCreate) -> Application:
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id == application_id).execution_options(ignore_tenant_scoping=True)
        application = (await self.session.execute(stmt)).scalar_one_or_none()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found.")
            
        if application.status.lower() != "returned":
            raise HTTPException(status_code=400, detail="Only returned applications can be resubmitted.")
            
        if application.email.lower() != application_in.email.lower():
            raise HTTPException(status_code=403, detail="Email address does not match the original application.")

        app_data = application_in.model_dump(exclude={"documents", "user_id", "tournament_id"})
        
        for key, value in app_data.items():
            setattr(application, key, value)
            
        application.status = "pending"
        application.reviewer_comments = None
        
        if application_in.documents:
            for doc in application.documents:
                await self.session.delete(doc)
            new_docs = [Document(**doc.model_dump(), application_id=application.id) for doc in application_in.documents]
            self.session.add_all(new_docs)
            
        await self.session.commit()
        await self.session.refresh(application)
        
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id == application.id).execution_options(ignore_tenant_scoping=True)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_application_by_id(self, application_id: uuid.UUID, bypass_tenant_scoping: bool = False) -> Application:
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id == application_id)
        if bypass_tenant_scoping:
            stmt = stmt.execution_options(ignore_tenant_scoping=True)
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

    async def _create_participant_from_application(self, application: Application, assigned_role: str | None):
        """Private helper to create a Participant if one doesn't already exist for the application."""
        # Automatically convert the Application into a Participant upon approval
        existing = await self.session.execute(select(Participant).where(Participant.application_id == application.id))
        if not existing.scalars().first():
            new_participant = Participant(
                application_id=application.id,
                tournament_id=application.tournament_id,
                role=assigned_role or application.category,
                organization_id=application.organization_id,
                sporting_disciplines=application.sporting_disciplines
            )
            self.session.add(new_participant)

    async def review_application(self, application_id: uuid.UUID, reviewer_id: uuid.UUID, review_data: ApplicationReview, bypass_tenant_scoping: bool = False) -> Application:
        application = await self.get_application_by_id(application_id, bypass_tenant_scoping=bypass_tenant_scoping)
        
        old_status = application.status
        application.status = review_data.status
        application.reviewer_comments = review_data.reviewer_comments
        application.reviewer_id = reviewer_id
        
        if review_data.status.lower() == "approved" and old_status != "approved":
            await self._create_participant_from_application(application, review_data.assigned_role)

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
            
            # 🔒 ZERO-TRUST: O(1) Cache Invalidation
            if self.redis:
                stmt = select(Participant.id).where(Participant.application_id == application.id)
                part_id = (await self.session.execute(stmt)).scalar()
                if part_id:
                    await self.redis.incr(f"participant_version:{part_id}")
            
        try:
            await self.session.commit()
            await self.session.refresh(application)
            return application
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="Invalid tournament ID provided. Please ensure the selected tournament exists.")

    async def review_applications_batch(self, reviewer_id: uuid.UUID, review_data: ApplicationBatchReview, bypass_tenant_scoping: bool = False) -> list[Application]:
        stmt = select(Application).options(selectinload(Application.documents)).where(Application.id.in_(review_data.application_ids))
        if bypass_tenant_scoping:
            stmt = stmt.execution_options(ignore_tenant_scoping=True)
        result = await self.session.execute(stmt)
        applications = list(result.scalars().all())
        
        if not applications:
            raise HTTPException(status_code=404, detail="No applications found.")

        changed_app_ids = []
        for application in applications:
            old_status = application.status
            application.status = review_data.status
            application.reviewer_comments = review_data.reviewer_comments
            application.reviewer_id = reviewer_id
            
            if review_data.status.lower() == "approved" and old_status != "approved":
                await self._create_participant_from_application(application, review_data.assigned_role)

            # Generate an Audit Log entry if the status was changed
            if old_status != review_data.status:
                changed_app_ids.append(application.id)
                audit_log = AuditLog(
                    entity_type="application",
                    entity_id=application.id,
                    action="status_change",
                    old_value=old_status,
                    new_value=review_data.status,
                    user_id=reviewer_id
                )
                self.session.add(audit_log)
                
        # 🔒 ZERO-TRUST: O(1) Cache Invalidation Pipeline
        if changed_app_ids and self.redis:
            stmt = select(Participant.id).where(Participant.application_id.in_(changed_app_ids))
            part_ids = (await self.session.execute(stmt)).scalars().all()
            if part_ids:
                pipeline = self.redis.pipeline()
                for pid in part_ids:
                    pipeline.incr(f"participant_version:{pid}")
                await pipeline.execute()
                
        try:
            await self.session.commit()
            for app in applications:
                await self.session.refresh(app)
            return applications
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=400, detail="Invalid tournament ID provided. Please ensure the selected tournament exists.")

    async def review_document(self, document_id: uuid.UUID, reviewer_id: uuid.UUID, review_data: DocumentReview, bypass_tenant_scoping: bool = False) -> Document:
        stmt = select(Document).where(Document.id == document_id)
        if bypass_tenant_scoping:
            stmt = stmt.execution_options(ignore_tenant_scoping=True)
        document = (await self.session.execute(stmt)).scalar_one_or_none()
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