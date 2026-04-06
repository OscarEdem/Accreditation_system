import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, ConfigDict

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

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

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

class UserInvite(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole
    organization_id: uuid.UUID | None = None

class AcceptInviteRequest(BaseModel):
    token: str
    new_password: str

class ResendInviteRequest(BaseModel):
    email: EmailStr