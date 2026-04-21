import uuid
from datetime import timedelta, datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead, UserMeResponse, ForgotPasswordRequest, ResetPasswordRequest, UserInvite, AcceptInviteRequest, ResendInviteRequest, UserRole, UserUpdateLanguage
from app.services.user import UserService
from app.services.token_blacklist import TokenBlacklistService
from app.core.security import create_access_token
from app.config.settings import settings
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.organization import Organization
from app.models.category import Category
from app.models.session_invalidation import SessionInvalidation
from app.workers.main import send_email_notification
import logging
from app.schemas.category import CategoryRead

logger = logging.getLogger(__name__)

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

def get_token_blacklist_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> TokenBlacklistService:
    return TokenBlacklistService(db, redis)

@router.post("/register", response_model=UserRead, status_code=201, summary="Register a New Applicant")
async def register_user(user_in: UserCreate, service: UserService = Depends(get_user_service)):
    """
    Registers a new public user. The system will forcibly assign the `applicant` role 
    for security purposes.
    """
    return await service.create_user(user_in)

@router.post("/login", response_model=Token, summary="Login & Get Access Token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis)
):
    """
    Authenticates a user and returns a JWT Bearer token valid for 30 minutes.
    
    **Frontend Implementation Notes:**
    - **IMPORTANT:** This endpoint expects `application/x-www-form-urlencoded` data, NOT standard JSON!
    - Use `URLSearchParams` or `FormData` when calling this via `fetch` or `axios`.
    
    **Example (Fetch API):**
    ```javascript
    const params = new URLSearchParams();
    params.append('username', 'user@example.com');
    params.append('password', 'secret123');
    
    fetch('/api/v1/auth/login', { method: 'POST', body: params });
    ```
    """
    # Brute Force Protection: Max 5 attempts per 5 minutes per email
    rate_limit_key = f"rate_limit:login:{form_data.username}"
    attempts = await redis.incr(rate_limit_key)
    if attempts == 1:
        await redis.expire(rate_limit_key, 300)  # 5-minute lockout window
    if attempts > 5:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts. Please try again in 5 minutes.")

    user = await service.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Clear the rate limit on successful login
    await redis.delete(rate_limit_key)
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated.")

    # Generate a unique session ID and store it in Redis as the active session
    session_id = str(uuid.uuid4())
    await redis.set(f"active_session:{user.id}", session_id, ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.email, 
            "session_id": session_id,
            "user_id": str(user.id),
            "role": getattr(user.role, "value", user.role),
            "org_id": str(user.organization_id) if user.organization_id else None
        }, 
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

async def _get_user_me_response(user: User, db: AsyncSession) -> UserMeResponse:
    """Helper to enrich the UserMeResponse with organization details."""
    org_name = None
    allowed_categories_list = []

    # System-level admins see all categories.
    if user.role in [UserRole.admin, UserRole.loc_admin, UserRole.officer]:
        all_categories_result = await db.execute(select(Category))
        allowed_categories_list = [CategoryRead.model_validate(c) for c in all_categories_result.scalars().all()]
    # Organization-level users are restricted.
    elif user.organization_id:
        org = await db.get(Organization, user.organization_id)
        if org:
            org_name = org.name
            if org.allowed_categories:
                stmt = select(Category).where(Category.name.in_(org.allowed_categories))
                allowed_categories_list = [CategoryRead.model_validate(c) for c in (await db.execute(stmt)).scalars().all()]
    # This is a data inconsistency - an org_admin should always have an org_id.
    elif user.role == UserRole.org_admin and not user.organization_id:
        logger.warning(f"Data Inconsistency: org_admin user {user.email} (ID: {user.id}) has no organization_id assigned.")
        allowed_categories_list = [] # Explicitly set to empty
            
    response = UserMeResponse.model_validate(user)
    response.organization_name = org_name
    response.allowed_categories = allowed_categories_list
    return response

@router.get("/me", response_model=UserMeResponse, summary="Get Current User Profile")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the profile of the currently authenticated user.
    
    **Frontend Implementation Notes:**
    - Pass the JWT token in the `Authorization: Bearer <token>` header.
    - This endpoint returns `organization_name` and an array of `allowed_categories`.
    - **Use Case:** Use `allowed_categories` to dynamically filter the Categories dropdown 
      in the frontend application form so users only see options their organization is permitted to apply for!
    """
    return await _get_user_me_response(current_user, db)

@router.patch("/me/language", response_model=UserMeResponse, summary="Update Preferred Language")
async def update_my_language(
    request: UserUpdateLanguage,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Allows a logged-in user to update their preferred language for the interface and email notifications.
    """
    current_user.preferred_language = request.preferred_language
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return await _get_user_me_response(current_user, db)

@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Redis = Depends(get_redis)
):
    await redis.set(f"active_session:{current_user.id}", "revoked", ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"message": "Successfully logged out."}

@router.post("/force-logout/{user_id}")
async def force_logout_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(allow_admin)],
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """Allows an Admin to instantly terminate a specific user's active session."""
    await redis.set(f"active_session:{user_id}", "revoked", ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    # Record session invalidation in DB for crash recovery
    invalidation = SessionInvalidation(
        user_id=user_id,
        session_id="all",
        reason="force_logout"
    )
    db.add(invalidation)
    await db.commit()
    
    return {"message": f"User session for {user_id} has been forcefully terminated."}

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, 
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis)
):
    # Rate Limiting: Max 3 requests per minute per email
    rate_limit_key = f"rate_limit:forgot_pwd:{request.email}"
    requests_made = await redis.incr(rate_limit_key)
    if requests_made == 1:
        await redis.expire(rate_limit_key, 60)  # 60-second window
    if requests_made > 3:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please wait a minute.")

    user = await service.get_user_by_email(request.email)
    if user:
        token = service.create_password_reset_token(user.email)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_email_notification.delay(
            recipient_email=user.email,
            template_key="forgot_password",
            language=user.preferred_language or 'en',
            context={"reset_link": reset_link}
        )
    return {"message": "If that email is registered, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    service: UserService = Depends(get_user_service),
    token_blacklist_service: TokenBlacklistService = Depends(get_token_blacklist_service),
    redis: Redis = Depends(get_redis)
):
    """
    Reset user password using a valid reset token.
    
    SECURITY:
    - Tokens are single-use; reuse is prevented via TokenBlacklist
    - Password change invalidates all active sessions
    - Uses timing-attack resistant password comparison
    """
    
    # Check if token has already been used (replay attack prevention)
    is_consumed = await token_blacklist_service.is_token_consumed(request.token)
    if is_consumed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link has already been used. Please request a new one."
        )
    
    # Verify token is valid and extract email
    user_service = UserService(db)
    email = user_service.verify_password_reset_token(request.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user and update password
    user = await user_service.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    await user_service.reset_password(request.token, request.new_password)
    
    # Blacklist the token immediately to prevent reuse
    # Token expires 1 hour from now (matching JWT token TTL)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await token_blacklist_service.consume_token(
        token=request.token,
        token_type="password_reset",
        expires_at=expires_at,
        user_id=user.id,
        reason="Password reset consumed"
    )
    
    # Invalidate all active sessions for this user (force re-login with new password)
    await redis.set(f"active_session:{user.id}", "revoked", ex=1800)
    
    # Record session invalidation in DB for crash recovery
    invalidation = SessionInvalidation(
        user_id=user.id,
        session_id="all",
        reason="password_change"
    )
    db.add(invalidation)
    await db.commit()
    
    logger.info(f"Password reset successful for user: {user.id}")
    
    return {"message": "Password successfully reset. Please log in with your new password."}

@router.post("/invite", response_model=UserRead, status_code=201)
async def invite_user(
    user_in: UserInvite,
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service)
):
    # SECURITY CHECK: Prevent LOC Admins from creating Super Admins (Privilege Escalation)
    if user_in.role == UserRole.admin and str(current_user.role) != "admin":
        raise HTTPException(status_code=403, detail="Only existing Super Admins can invite other Super Admins.")

    # Enforce Organization requirements based on Role
    if user_in.role == UserRole.org_admin:
        if not user_in.organization_id:
            raise HTTPException(status_code=400, detail="An Organization must be selected for the org_admin role.")
    else:
        # Ensure system admins/staff don't get tied to a participant organization. (Applicants can optionally have one).
        if user_in.role != UserRole.applicant:
            user_in.organization_id = None

    user = await service.invite_user(user_in)
    
    token = service.create_invite_token(user.email)
    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    resend_link = f"{settings.FRONTEND_URL}/resend-invite"
    
    send_email_notification.delay(
        recipient_email=user.email,
        template_key="user_invite",
        language=user.preferred_language or 'en',
        context={
            "first_name": user.first_name,
            "role": user_in.role.value,
            "invite_link": invite_link,
            "resend_link": resend_link
        }
    )
    return user

@router.post("/accept-invite")
async def accept_invite(
    request: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
    service: UserService = Depends(get_user_service),
    token_blacklist_service: TokenBlacklistService = Depends(get_token_blacklist_service),
    redis: Redis = Depends(get_redis)
):
    """
    Accept an invite and set initial password.
    
    SECURITY:
    - Invite tokens are single-use; reuse is prevented via TokenBlacklist
    - After successful activation, token cannot be used again
    """
    
    # Check if token has already been used (replay attack prevention)
    is_consumed = await token_blacklist_service.is_token_consumed(request.token)
    if is_consumed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has already been used. Please request a new one."
        )
    
    # Verify token is valid and extract email
    user_service = UserService(db)
    email = user_service.verify_invite_token(request.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token"
        )
    
    # Accept invite and set password
    if not await user_service.accept_invite(request.token, request.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to accept invite"
        )
    
    # Get user for logging
    user = await user_service.get_user_by_email(email)
    
    # Blacklist the token immediately to prevent reuse
    # Token expires 24 hours from now (matching JWT token TTL)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await token_blacklist_service.consume_token(
        token=request.token,
        token_type="invite",
        expires_at=expires_at,
        user_id=user.id if user else None,
        reason="Invite accepted"
    )
    
    logger.info(f"Invite accepted for user: {email}")
    
    return {"message": "Password successfully set. You can now log in."}

@router.post("/resend-invite")
async def resend_invite(
    request: ResendInviteRequest, 
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis)
):
    # Rate Limiting: Max 3 requests per minute per email
    rate_limit_key = f"rate_limit:resend_invite:{request.email}"
    requests_made = await redis.incr(rate_limit_key)
    if requests_made == 1:
        await redis.expire(rate_limit_key, 60)  # 60-second window
    if requests_made > 3:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please wait a minute.")

    user = await service.get_user_by_email(request.email)
    if user:
        token = service.create_invite_token(user.email)
        invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
        
        send_email_notification.delay(
            recipient_email=user.email,
            template_key="resend_invite",
            language=user.preferred_language or 'en',
            context={
                "first_name": user.first_name,
                "invite_link": invite_link
            }
        )
    return {"message": "If that email is registered, a new invite link has been sent."}