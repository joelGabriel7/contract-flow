from datetime import datetime
from typing import List
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from .base import TimestampModel
from .types import OrganizationRole


class OrganizationBase(SQLModel):
    name: str = Field(index=True)


class Organization(OrganizationBase, TimestampModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    members: List["OrganizationUser"] = Relationship(
        back_populates="organization")
    invitations: List['Invitation'] = Relationship(
        back_populates="organization")

    def get_user_role(self, user_id: UUID):
        for member in self.members:
            if member.user_id == user_id:
                return member.role
        return None

    @property
    def total_members(self) -> int:
        return len(self.members)

    @property
    def admins(self) -> List["User"]:
        return [m.user for m in self.members if m.role == OrganizationRole.ADMIN]


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
