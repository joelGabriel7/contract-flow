from typing import Optional, List, Dict
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


# Dashboard schemas to organization

class DashboardMemberInfo(OrganizationMemberRead):
    email: str
    full_name: Optional[str]
    is_verified: bool


class DashboardMetrics(SQLModel):
    total_members: int
    members_by_role: Dict[OrganizationRole, int]
    active_invitations: int


class AdminDashboardResponse(SQLModel):
    organization: OrganizationRead
    metrics: DashboardMetrics
    members: List[DashboardMemberInfo]

# app/schemas/organization.py


class RoleUpdate(SQLModel):
    role: OrganizationRole
