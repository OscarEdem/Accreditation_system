import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Literal
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
    preferred_language: Literal['en', 'fr', 'pt', 'es', 'ar'] = 'en'

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str) -> str:
        if any(char.isdigit() for char in v):
            raise ValueError("Names cannot contain numbers.")
        return v

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserMeResponse(UserRead):
    organization_name: Optional[str] = None
    allowed_categories: List[str] = []

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
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

class UserInvite(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole
    organization_id: uuid.UUID | None = None
    preferred_language: Literal['en', 'fr', 'pt', 'es', 'ar'] = 'en'

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v: str) -> str:
        if any(char.isdigit() for char in v):
            raise ValueError("Names cannot contain numbers.")
        return v

class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("Password must contain at least one special character.")
        return v

class ResendInviteRequest(BaseModel):
    email: EmailStr