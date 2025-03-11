from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel, Field
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


class SecuritySettings(SQLModel):
    require_2fa: bool = False
    session_timeout_minutes: int = 60
    password_expiry_days: Optional[int] = None
    ip_restrictions: Optional[List[str]] = None


class NotificationSettings(SQLModel):
    email_digest: bool = True
    new_member_alerts: bool = True
    contract_updates: bool = True
    daily_summary: bool = True


class StorageSettings(SQLModel):
    limit_gb: int = 50
    auto_delete_days: Optional[int] = None
    allow_external_sharing: bool = False


class OrganizationSettings(SQLModel):
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)


class OrganizationSettingsUpdate(SQLModel):
    security: Optional[SecuritySettings] = None
    notifications: Optional[NotificationSettings] = None
    storage: Optional[StorageSettings] = None


class OrganizationDetailResponse(SQLModel):
    organization: OrganizationRead
    settings: OrganizationSettings
