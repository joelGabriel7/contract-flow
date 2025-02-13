from typing import Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel
from ..models.types import AccountType

class UserCreate(SQLModel):
    email: str
    password: str
    full_name: Optional[str] = None
    account_type: AccountType
    organization_name: Optional[str] = None

class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

class UserRead(SQLModel):
    id: UUID
    email: str
    full_name: Optional[str]
    account_type: AccountType
    is_verified: bool
    created_at: datetime