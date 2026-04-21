import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Literal
import re
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, ValidationInfo
from app.schemas.category import CategoryRead
from app.schemas.validators import validate_password_strength, validate_name

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
    preferred_language: Literal['en', 'fr', 'pt', 'es', 'ar'] = 'en'

    @field_validator('first_name')
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        return validate_name(v, "First name")
    
    @field_validator('last_name')
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return validate_name(v, "Last name")

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserMeResponse(UserRead):
    organization_name: Optional[str] = None
    allowed_categories: List[CategoryRead] = []

class UserListResponse(BaseModel):
    total: int
    items: List[UserRead]

class UserUpdateRole(BaseModel):
    role: UserRole
    organization_id: uuid.UUID | None = None

class UserUpdateStatus(BaseModel):
    is_active: bool

class UserUpdateLanguage(BaseModel):
    preferred_language: Literal['en', 'fr', 'pt', 'es', 'ar'] = 'en'

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class UserInvite(UserBase):
    # Inherits all fields from UserBase and its validators.
    # We only override 'role' to remove the default value, making it a required field for invites.
    role: UserRole

class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

class ResendInviteRequest(BaseModel):
    email: EmailStr