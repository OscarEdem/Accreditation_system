import uuid
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.user import User
from app.schemas.user import UserCreate, UserInvite
from app.core.security import get_password_hash, verify_password
from app.config.settings import settings

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_in: UserCreate) -> User:
        if await self.get_user_by_email(user_in.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        user_data = user_in.model_dump()
        password = user_data.pop("password")
        
        # Force new registered users to be 'applicant', preventing privilege escalation attacks
        user_data["role"] = "applicant"
        user_data["organization_id"] = None
        
        user = User(**user_data, password_hash=get_password_hash(password))
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def invite_user(self, user_in: UserInvite) -> User:
        if await self.get_user_by_email(user_in.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        user_data = user_in.model_dump()
        
        # Generate a strong, unusable random password. The user will set their own via the invite link.
        dummy_password = secrets.token_urlsafe(32)
        
        user = User(**user_data, password_hash=get_password_hash(dummy_password))
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    def create_password_reset_token(self, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        to_encode = {"exp": expire, "sub": email, "type": "password_reset"}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def verify_password_reset_token(self, token: str) -> str | None:
        try:
            decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if decoded.get("type") != "password_reset":
                return None
            return decoded.get("sub")
        except jwt.InvalidTokenError:
            return None

    def create_invite_token(self, email: str) -> str:
        # Invite tokens are valid for 24 hours
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        to_encode = {"exp": expire, "sub": email, "type": "invite"}
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def verify_invite_token(self, token: str) -> str | None:
        try:
            decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if decoded.get("type") != "invite":
                return None
            return decoded.get("sub")
        except jwt.InvalidTokenError:
            return None

    async def accept_invite(self, token: str, new_password: str) -> bool:
        email = self.verify_invite_token(token)
        if not email:
            return False
        user = await self.get_user_by_email(email)
        if not user:
            return False
        user.password_hash = get_password_hash(new_password)
        await self.session.commit()
        return True
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        email = self.verify_password_reset_token(token)
        if not email:
            return False
        user = await self.get_user_by_email(email)
        if not user:
            return False
        user.password_hash = get_password_hash(new_password)
        await self.session.commit()
        return True
    
    async def authenticate_user(self, email: str, password: str) -> User | None:
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            return None
        return user

    async def update_user_role(self, user_id: uuid.UUID, role: str, organization_id: uuid.UUID | None = None) -> User:
        user = await self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = role
        user.organization_id = organization_id
        
        await self.session.commit()
        await self.session.refresh(user)
        return user