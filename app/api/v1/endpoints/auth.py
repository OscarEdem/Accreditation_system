from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead, ForgotPasswordRequest, ResetPasswordRequest
from app.services.user import UserService
from app.core.security import create_access_token
from app.config.settings import settings
from app.api.deps import get_current_user
from app.models.user import User
from app.workers.main import send_email_notification

router = APIRouter()

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

@router.post("/register", response_model=UserRead, status_code=201)
async def register_user(user_in: UserCreate, service: UserService = Depends(get_user_service)):
    return await service.create_user(user_in)

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: UserService = Depends(get_user_service)
):
    user = await service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer")

@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, service: UserService = Depends(get_user_service)):
    user = await service.get_user_by_email(request.email)
    if user:
        token = service.create_password_reset_token(user.email)
        reset_link = f"https://accra2026.com/reset-password?token={token}"
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