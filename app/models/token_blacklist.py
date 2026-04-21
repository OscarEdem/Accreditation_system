import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import BaseModel


class TokenBlacklist(BaseModel):
    """
    Token blacklist for preventing replay attacks on single-use tokens.
    
    When password reset, invite, or other single-use tokens are consumed,
    their hash is recorded here with TTL matching the token expiry.
    
    This prevents attackers from:
    - Using intercepted password reset links multiple times
    - Sharing invite tokens with multiple users
    - Reusing tokens after credential changes
    
    Implementation:
    1. Token is consumed by user (e.g., password reset)
    2. Token hash is added to this table
    3. On subsequent use attempts, we check if hash is in blacklist
    4. If found, reject with "token already used"
    5. DB records auto-delete after expiry (via scheduled cleanup job)
    """
    __tablename__ = "token_blacklist"

    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA256 hex = 64 chars
        unique=True,
        index=True,
        nullable=False,
        comment="SHA256 hash of the token"
    )
    token_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g., 'password_reset', 'invite', 'email_verification'"
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="NULL for pre-user tokens like invites"
    )
    consumed_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Token expiry time; records auto-delete after this"
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why token was consumed/blacklisted"
    )

    # Composite index for cleanup queries
    __table_args__ = (
        Index('ix_token_blacklist_expires_at_type', 'expires_at', 'token_type'),
    )
