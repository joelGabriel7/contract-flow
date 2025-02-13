from datetime import datetime
from typing import List
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from .base import TimestampModel
from .types import OrganizationRole
from .users import User

class OrganizationBase(SQLModel):
    name: str = Field(index=True)

class Organization(OrganizationBase, TimestampModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Relationships
    members: List["OrganizationUser"] = Relationship(back_populates="organization")

class OrganizationUser(SQLModel, table=True):
    organization_id: UUID = Field(
        foreign_key="organization.id", 
        primary_key=True
    )
    user_id: UUID = Field(
        foreign_key="user.id", 
        primary_key=True
    )
    role: OrganizationRole = Field(default=OrganizationRole.VIEWER)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    organization: Organization = Relationship(back_populates="members")
    user: "User" = Relationship(back_populates="organizations")