from typing import Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel
from ..models.types import AccountType,OrganizationRole

class OrganizationInfo(SQLModel):
    id: UUID
    name: str
    role: OrganizationRole
    total_members: int
\

class UserCreate(SQLModel):
    email: str
    password: str
    full_name: Optional[str] = None
    account_type: AccountType
    organizations: Optional[str] = None

class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class UserRead(SQLModel):
    id: UUID
    email: str
    full_name: Optional[str]
    account_type: AccountType
    organization: Optional[OrganizationInfo] = None
    is_verified: bool
    is_active: bool
    created_at: datetime