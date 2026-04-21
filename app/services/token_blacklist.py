import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.models.token_blacklist import TokenBlacklist
from app.models.user import User


class TokenBlacklistService:
    """
    Manages single-use token blacklisting to prevent replay attacks.
    
    Implements dual-layer protection:
    1. Redis cache (fast, ~1ms) for immediate rejection
    2. PostgreSQL fallback for persistence across Redis restarts
    """
    
    def __init__(self, db: AsyncSession, redis: Optional[Redis] = None):
        self.db = db
        self.redis = redis
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Generate SHA256 hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    async def is_token_consumed(self, token: str) -> bool:
        """
        Check if token has already been used.
        
        Returns True if token is in blacklist (consumed).
        Returns False if token is still valid.
        """
        token_hash = self.hash_token(token)
        
        # Layer 1: Check Redis cache first (fast path)
        if self.redis:
            is_consumed = await self.redis.get(f"token_consumed:{token_hash}")
            if is_consumed:
                return True
        
        # Layer 2: Check PostgreSQL blacklist (fallback)
        blacklist_entry = await self.db.scalar(
            select(TokenBlacklist).where(TokenBlacklist.token_hash == token_hash)
        )
        
        if blacklist_entry:
            # Token is in blacklist - cache this result for 5 minutes
            if self.redis:
                await self.redis.set(
                    f"token_consumed:{token_hash}",
                    "consumed",
                    ex=300  # 5-minute cache
                )
            return True
        
        return False
    
    async def consume_token(
        self,
        token: str,
        token_type: str,
        expires_at: datetime,
        user_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> TokenBlacklist:
        """
        Mark token as consumed/blacklisted.
        
        Args:
            token: The token string to blacklist
            token_type: Type of token (e.g., 'password_reset', 'invite')
            expires_at: When the token expires
            user_id: User ID (may be None for pre-user tokens like invites)
            reason: Why token was consumed (optional)
        
        Returns:
            TokenBlacklist record created
        """
        token_hash = self.hash_token(token)
        
        # Ensure expires_at is naive before subtracting to prevent TypeError
        if expires_at.tzinfo:
            expires_at = expires_at.replace(tzinfo=None)
        # Calculate TTL for both cache and DB
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        ttl_seconds = int((expires_at - now).total_seconds())
        
        # Ensure TTL is at least 1 second
        ttl_seconds = max(1, ttl_seconds)
        
        # Record in database
        blacklist_entry = TokenBlacklist(
            token_hash=token_hash,
            token_type=token_type,
            user_id=user_id,
            consumed_at=now,
            expires_at=expires_at,
            reason=reason
        )
        self.db.add(blacklist_entry)
        await self.db.commit()
        
        # Cache in Redis for faster future checks
        if self.redis:
            await self.redis.set(
                f"token_consumed:{token_hash}",
                "consumed",
                ex=ttl_seconds
            )
        
        return blacklist_entry
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired entries from token_blacklist table.
        
        Should be called periodically (e.g., daily) via background job.
        
        Returns:
            Number of records deleted
        """
        from sqlalchemy import delete
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self.db.execute(
            delete(TokenBlacklist).where(TokenBlacklist.expires_at < now)
        )
        await self.db.commit()
        
        return result.rowcount or 0
