import uuid
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead, UserMeResponse, ForgotPasswordRequest, ResetPasswordRequest, UserInvite, AcceptInviteRequest, ResendInviteRequest, UserRole
from app.services.user import UserService
from app.core.security import create_access_token
from app.config.settings import settings
from app.api.deps import get_current_user, RoleChecker
from app.models.user import User
from app.models.organization import Organization
from app.workers.main import send_email_notification
from app.core.constants import ORG_ALLOWED_CATEGORIES

router = APIRouter()

allow_admin = RoleChecker(["admin", "loc_admin"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

@router.post("/register", response_model=UserRead, status_code=201)
async def register_user(user_in: UserCreate, service: UserService = Depends(get_user_service)):
    return await service.create_user(user_in)

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserService = Depends(get_user_service),
    redis: Redis = Depends(get_redis)
):
    user = await service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated.")

    # Generate a unique session ID and store it in Redis as the active session
    session_id = str(uuid.uuid4())
    await redis.set(f"active_session:{user.id}", session_id, ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email, "session_id": session_id}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer")

@router.get("/me", response_model=UserMeResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    org_name = None
    allowed_categories = []
    if current_user.organization_id:
        org = await db.get(Organization, current_user.organization_id)
        if org:
            org_name = org.name
            allowed_categories = ORG_ALLOWED_CATEGORIES.get(org.name, [])
            
    response = UserMeResponse.model_validate(current_user)
    response.organization_name = org_name
    response.allowed_categories = allowed_categories
    return response

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
    redis: Redis = Depends(get_redis)
):
    """Allows an Admin to instantly terminate a specific user's active session."""
    await redis.set(f"active_session:{user_id}", "revoked", ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
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
            subject="Accra 2026 - Password Reset Request",
            body=f"Click the following link to reset your password. It expires in 1 hour:\n\n{reset_link}"
        )
    return {"message": "If that email is registered, a password reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, service: UserService = Depends(get_user_service)):
    if not await service.reset_password(request.token, request.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return {"message": "Password successfully reset."}

@router.post("/invite", response_model=UserRead, status_code=201)
async def invite_user(
    current_user: Annotated[User, Depends(allow_admin)],
    service: UserService = Depends(get_user_service),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: EmailStr = Form(...),
    role: UserRole = Form(...),
    organization_id: str | None = Form(None)
):
    # Safely convert an empty string from the Swagger UI form into a valid None
    org_uuid = None
    if organization_id and organization_id.strip():
        try:
            org_uuid = uuid.UUID(organization_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization_id format")
            
    # Enforce Organization requirements based on Role
    if role in [UserRole.org_admin, UserRole.applicant]:
        if not org_uuid:
            raise HTTPException(status_code=400, detail=f"An Organization must be selected for the {role.value} role.")
    else:
        org_uuid = None  # Ensure system admins/staff don't get tied to a participant organization
            
    user_in = UserInvite(
        first_name=first_name,
        last_name=last_name,
        email=email,
        role=role,
        organization_id=org_uuid
    )
    user = await service.invite_user(user_in)
    
    token = service.create_invite_token(user.email)
    invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    resend_link = f"{settings.FRONTEND_URL}/resend-invite"
    
    send_email_notification.delay(
        recipient_email=user.email,
        subject="ACCRA 2026 - Account Invitation",
        body=(
            f"Hello {user.first_name},\n\n"
            f"You have been invited as a '{user_in.role.value}' for ACCRA 2026.\n"
            f"Click here to set your password and access your account (valid for 24 hours):\n{invite_link}\n\n"
            f"If this link has expired, you can request a new one here:\n{resend_link}"
        )
    )
    return user

@router.post("/accept-invite")
async def accept_invite(request: AcceptInviteRequest, service: UserService = Depends(get_user_service)):
    if not await service.accept_invite(request.token, request.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite token")
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
            subject="ACCRA 2026 - New Account Invitation",
            body=f"Hello {user.first_name},\n\nA new invitation link has been generated for your ACCRA 2026 account.\nClick here to set your password (valid for 24 hours):\n{invite_link}"
        )
    return {"message": "If that email is registered, a new invite link has been sent."}