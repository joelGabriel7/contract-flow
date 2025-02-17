# app/models/invitation.py
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, Relationship
from .base import TimestampModel
from .types import OrganizationRole

class Invitation(TimestampModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organization.id")
    email: str = Field(index=True)
    role: OrganizationRole
    token: str = Field(unique=True)
    expires_at: datetime
    
    # Relación con la organización
    organization: "Organization" = Relationship(back_populates="invitations")