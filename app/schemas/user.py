import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
import re
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, ValidationInfo

class UserRole(str, Enum):
    applicant = "applicant"
    admin = "admin"
    loc_admin = "loc_admin"
    officer = "officer"
    org_admin = "org_admin"
    scanner = "scanner"

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole = UserRole.applicant
    is_active: bool = True
    organization_id: uuid.UUID | None = None

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must be at least 8 characters long, contain an uppercase letter, and a number.")
        return v

class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserMeResponse(UserRead):
    organization_name: Optional[str] = None
    allowed_categories: Optional[List[str]] = None

class UserListResponse(BaseModel):
    total: int
    items: List[UserRead]

class UserUpdateRole(BaseModel):
    role: UserRole
    organization_id: uuid.UUID | None = None

class UserUpdateStatus(BaseModel):
    is_active: bool

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must be at least 8 characters long, contain an uppercase letter, and a number.")
        return v

class UserInvite(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole
    organization_id: uuid.UUID | None = None

class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must be at least 8 characters long, contain an uppercase letter, and a number.")
        return v

class ResendInviteRequest(BaseModel):
    email: EmailStr