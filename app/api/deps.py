from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.config.settings import settings
from app.db.session import get_db
from app.db.redis import get_redis
from app.models.user import User
from app.models.session_invalidation import SessionInvalidation
from app.services.user import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> User:
    """
    Validate JWT token and verify session is still active.
    
    SECURITY: Uses dual-layer validation:
    1. Redis cache (fast, ~1ms) for most requests
    2. PostgreSQL fallback (for Redis recovery) to prevent bypass after crashes
    
    This prevents attackers from regaining access after:
    - Admin force-logout
    - Password change
    - Role change
    - Redis restart
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str | None = payload.get("sub")
        session_id: str | None = payload.get("session_id")
        if email is None or session_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    user = await UserService(db).get_user_by_email(email)
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated.")
    
    # Layer 1: Check Redis cache (fast path, ~1ms)
    active_session = await redis.get(f"active_session:{user.id}")
    
    # Redis returns bytes by default, so we must decode it back to a string
    if active_session and isinstance(active_session, bytes):
        active_session = active_session.decode("utf-8")
    
    if active_session:
        # Session exists in cache
        if active_session == "revoked" or active_session != session_id:
            raise credentials_exception
        return user
    
    # Layer 2: Check persistent PostgreSQL blacklist (fallback, handles Redis loss)
    invalidation = await db.scalar(
        select(SessionInvalidation).where(
            (SessionInvalidation.user_id == user.id) &
            (SessionInvalidation.session_id.in_([session_id, "all"]))
        )
    )
    
    if invalidation:
        # Session was explicitly invalidated (force logout, password change, etc.)
        raise credentials_exception
    
    # Session is valid but not in Redis (e.g., after Redis restart)
    # Restore to cache with original TTL
    await redis.set(
        f"active_session:{user.id}",
        session_id,
        ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user


class RateLimiter:
    """
    Generic rate limiting dependency.
    Usage: @router.post("/endpoint", dependencies=[Depends(RateLimiter(requests=5, window=60))])
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request, redis: Redis = Depends(get_redis)):
        identifier = request.client.host if request.client else "unknown"
        
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, options={"verify_signature": False})
                if payload.get("user_id"):
                    identifier = f"user:{payload.get('user_id')}"
            except Exception:
                pass

        rate_limit_key = f"rate_limit:{request.url.path}:{identifier}"
        
        requests_made = await redis.incr(rate_limit_key)
        if requests_made == 1:
            await redis.expire(rate_limit_key, self.window)
            
        if requests_made > self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )