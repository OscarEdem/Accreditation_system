import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel


class SessionInvalidation(BaseModel):
    """
    Persistent session invalidation tracking.
    
    Used to survive Redis restarts and prevent users from accessing
    the system after their sessions are force-logged-out or credentials
    are changed.
    
    When a session is invalidated:
    1. Record added to this table with TTL matching token expiry
    2. Redis cache is updated
    3. On each request, both Redis and DB are checked
    
    This prevents the vulnerability where Redis restart allows
    force-logged-out users to regain access.
    """
    __tablename__ = "session_invalidations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True
    )
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    invalidated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="e.g., 'force_logout', 'password_change', 'role_change'"
    )

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_session_invalidations_user_session', 'user_id', 'session_id'),
    )
