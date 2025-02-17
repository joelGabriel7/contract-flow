
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel
from ..models.types import OrganizationRole

class InvitationCreate(SQLModel):
    email: str
    role: OrganizationRole
    message: Optional[str] = None

class InvitationResponse(SQLModel):
    id: UUID
    email: str
    role: OrganizationRole
    expires_at: datetime
    organization_name: str

class InvitationAccept(SQLModel):
    token: str