from typing import Optional, List
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel
from ..models.types import OrganizationRole

class OrganizationCreate(SQLModel):
    name: str

class OrganizationUpdate(SQLModel):
    name: Optional[str] = None

class OrganizationRead(SQLModel):
    id: UUID
    name: str
    created_at: datetime
    
class OrganizationMemberRead(SQLModel):
    user_id: UUID
    role: OrganizationRole
    joined_at: datetime

class OrganizationWithMembers(OrganizationRead):
    members: List[OrganizationMemberRead]