"""
    Organization Management API Documentation

    Overview
    This module implements a FastAPI router for managing organizations, providing endpoints for organization administration, member management, invitations, and settings configuration.

    Key Features
    - Organization dashboard and metrics
    - Member management (roles, removal)
    - Invitation system
    - Settings management
    - Permission-based access control

    Endpoints

    Organization Details
    - `GET /organizations/me`
    - Returns current user's organization details
    - Requires `EDIT_ORGANIZATION` permission
    - Returns: Organization info and settings

    Dashboard
    - `GET /organizations/{org_id}/dashboard`
    - Retrieves admin dashboard data
    - Includes member statistics and metrics
    - Requires `EDIT_ORGANIZATION` permission

    Member Management
    - `PUT /organizations/{org_id}/members/change-role/{user_id}`
    - Updates member roles
    - Sends email notification
    - Prevents self-role modification
    - Requires `EDIT_ORGANIZATION` permission

    - `DELETE /organizations/{org_id}/members/{user_id}`
    - Removes organization members
    - Validates admin count
    - Sends removal notification
    - Requires `REMOVE_MEMBERS` permission

    Invitation System
    - `POST /organizations/{org_id}/invitations`
    - Creates new member invitations
    - Validates existing membership/invitations
    - Sends different emails for registered/unregistered users
    - Requires `INVITE_MEMBERS` permission

    - `GET /organizations/{org_id}/invitations`
    - Lists pending invitations
    - Requires `INVITE_MEMBERS` permission

    - `DELETE /organizations/{org_id}/invitations/{invitation_id}`
    - Cancels pending invitations
    - Sends cancellation notification
    - Requires `INVITE_MEMBERS` permission

    Settings Management
    - `GET /organizations/{org_id}/settings`
    - Retrieves organization settings
    - Includes storage usage metrics
    - Requires `EDIT_ORGANIZATION` permission

    - `PUT /organizations/{org_id}/settings`
    - Updates organization settings
    - Validates storage limits
    - Maintains existing settings
    - Requires `EDIT_ORGANIZATION` permission

    Security Features
    - Permission-based access control using decorators
    - Role validation for critical operations
    - Protection against self-role modification
    - Storage limit validation
    - Last admin removal prevention

    Email Notifications
    The system sends automated emails for:
    - New invitations (different templates for registered/unregistered users)
    - Invitation cancellations
    - Member removals
    - Role updates
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from uuid import UUID
from typing import List, Optional

from ..core.permission import require_permission, Permission
from ..core.security import get_current_user, get_session, get_current_user_with_org
from ..schemas.organization import AdminDashboardResponse, OrganizationRead, DashboardMemberInfo, DashboardMetrics, RoleUpdate, OrganizationSettings, OrganizationSettingsUpdate, OrganizationDetailResponse
from ..schemas.invitations import InvitationResponse, InvitationCreate
from ..models.users import User
from ..models.invitations import Invitation
from ..models.organization import Organization, OrganizationUser, OrganizationRole
from ..services.email_services import email_service

import secrets
from datetime import datetime, timedelta


router = APIRouter()


@router.get("/me", response_model=OrganizationDetailResponse)
@require_permission(Permission.EDIT_ORGANIZATION)
async def get_my_organization(
    current_data: tuple[User, Optional[Organization]] = Depends(get_current_user_with_org)
):
    """
        Retrieve the current user's organization details.

        This asynchronous function fetches the organization associated with the
        current user. If no organization is found, it raises an HTTP 404 error.
        Returns an `OrganizationDetailResponse` containing the organization's
        basic information and settings.

        Args:
            current_data (tuple[User, Optional[Organization]]): A tuple containing
            the current user and their associated organization, obtained via dependency
            injection.

        Returns:
            OrganizationDetailResponse: The response model containing the organization's
            details and settings.

        Raises:
            HTTPException: If no organization is found for the current user.
    """
    user, organization = current_data

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="No organization found for current user"
        )

    return OrganizationDetailResponse(
        organization=OrganizationRead(
            id=organization.id,
            name=organization.name,
            created_at=organization.created_at
        ),
        settings=organization.settings
    )

@router.get("/{org_id}/dashboard", response_model=AdminDashboardResponse)
@require_permission(Permission.EDIT_ORGANIZATION)
async def admin_dashboard(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieves and compiles organization dashboard data for administrators.

    Fetches organization details, member information, and metrics including role distribution
    and active invitations. Returns a structured AdminDashboardResponse with organization data,
    metrics, and detailed member information.

    Args:
        org_id: UUID of the organization to retrieve dashboard data for
        current_user: Authenticated user making the request
        session: Database session for executing queries

    Returns:
        AdminDashboardResponse containing organization details, metrics, and member information

    Raises:
        HTTPException: If organization with the provided ID is not found (404)
    """

    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    members_query = select(OrganizationUser, User).join(
        User, OrganizationUser.user_id == User.id
    ).where(OrganizationUser.organization_id == org_id)

    members = session.exec(members_query).all()

    total_members = len(members)
    members_by_role = {}
    for org_user, _ in members:
        role = org_user.role
        members_by_role[role] = members_by_role.get(role, 0) + 1

    active_invitations = len(session.exec(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.expires_at > datetime.utcnow()
        )
    ).all())

    return AdminDashboardResponse(
        organization=OrganizationRead(
            id=organization.id,
            name=organization.name,
            created_at=organization.created_at
        ),
        metrics=DashboardMetrics(
            total_members=total_members,
            members_by_role=members_by_role,
            active_invitations=active_invitations
        ),
        members=[
            DashboardMemberInfo(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=org_user.role,
                joined_at=org_user.joined_at,
                is_verified=user.is_verified
            )
            for org_user, user in members
        ]
    )


@router.post("/{org_id}/invitations", response_model=InvitationResponse)
@require_permission(Permission.INVITE_MEMBERS)
async def create_invitation(
    org_id: UUID,
    invitation_data: InvitationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):

    """
    Creates a new invitation for a user to join an organization and sends an email notification.

    Args:
        org_id: UUID of the organization
        invitation_data: Data for creating the invitation including email and role
        background_tasks: FastAPI background tasks handler
        current_user: Currently authenticated user
        session: Database session

    Returns:
        InvitationResponse with the created invitation details

    Raises:
        HTTPException: If organization not found, user is already a member, or pending invitation exists
    """

    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verificar si el usuario ya es miembro
    existing_member = session.exec(
        select(OrganizationUser).join(User).where(
            User.email == invitation_data.email,
            OrganizationUser.organization_id == org_id
        )
    ).first()

    if existing_member:
        raise HTTPException(
            status_code=400,
            detail="User is already a member of this organization"
        )

    # Verificar si ya existe una invitación pendiente
    existing_invitation = session.exec(
        select(Invitation).where(
            Invitation.email == invitation_data.email,
            Invitation.organization_id == org_id,
            Invitation.expires_at > datetime.utcnow()
        )
    ).first()

    if existing_invitation:
        raise HTTPException(
            status_code=400,
            detail="An invitation is already pending for this email"
        )
    user_exits = session.exec(
        select(User).where(User.email == invitation_data.email)
    ).first() is not None
    # Crear nueva invitación
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    invitation = Invitation(
        organization_id=org_id,
        email=invitation_data.email,
        role=invitation_data.role,
        token=token,
        expires_at=expires_at
    )

    session.add(invitation)
    session.commit()
    session.refresh(invitation)

    if user_exits:
        background_tasks.add_task(
            email_service.send_invitation_email,
            to_email=invitation_data.email,
            organization_name=organization.name,
            inviter_name=current_user.full_name,
            invitation_token=token,
            role=invitation_data.role,
            custom_message=invitation_data.message
        )
    else:
        background_tasks.add_task(
            email_service.send_invitation_to_unregistered_email,
            to_email=invitation_data.email,
            organization_name=organization.name,
            inviter_name=current_user.full_name,
            invitation_token=token,
            role=invitation_data.role,
            custom_message=invitation_data.message
        )

    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        organization_name=organization.name
    )


@router.get('{org_id}/invitations', response_model=List[InvitationResponse])
@require_permission(Permission.INVITE_MEMBERS)
async def list_pending_invitations(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Retrieves all active pending invitations for a specific organization.

    Args:
        org_id: UUID of the organization
        current_user: Authenticated user from token
        session: Database session

    Returns:
        List of InvitationResponse objects containing invitation details
    """
    invitations = session.exec(
        select(Invitation).where(
            Invitation.organization_id == org_id,
            Invitation.expires_at > datetime.utcnow()
        )
    ).all()

    organization = session.get(Organization, org_id)

    return [
        InvitationResponse(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            expires_at=invitation.expires_at,
            organization_name=organization.name

        ) for invitation in invitations
    ]


@router.delete('/{org_id}/invitations/{invitation_id}')
@require_permission(Permission.INVITE_MEMBERS)
async def cancel_invitation(
    org_id: UUID,
    invitation_id: UUID,
    user_id: UUID,
    background_task: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):

    """
    Cancels an organization invitation and notifies the user via email.

    Args:
        org_id (UUID): Organization identifier
        invitation_id (UUID): Invitation identifier
        user_id (UUID): User identifier
        background_task (BackgroundTasks): FastAPI background task handler
        current_user (User): Currently authenticated user
        session (Session): Database session

    Returns:
        dict: Success message on successful cancellation

    Raises:
        HTTPException: If invitation not found or error during cancellation
    """
    invitation = session.get(Invitation, invitation_id)
    user = session.get(User, user_id)
    organization = session.get(Organization, org_id)
    if not invitation or invitation.organization_id != org_id:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found"
        )

    try:
        session.delete(invitation)

        background_task.add_task(
            email_service.send_invitation_cancelled_email,
            to_email=user.email,
            organization_name=organization.name
        )
        session.commit()
        return {"message": " Invitation cancelled successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelling invitation: \n {str(e)}"
        )


@router.delete('/{org_id}/members/{user_id}')
@require_permission(Permission.REMOVE_MEMBERS)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),

):
    """
    Removes a member from an organization with validation checks and email notification.

    Args:
        org_id (UUID): Organization identifier
        user_id (UUID): User identifier to remove
        background_tasks (BackgroundTasks): Task queue for async email sending
        session (Session): Database session
        current_user (User): Currently authenticated user

    Raises:
        HTTPException: If member not found, trying to remove self, removing last admin,
                    or database error occurs

    Returns:
        dict: Success message confirmation
    """
    org_user = session.exec(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id
        )
    ).first()

    if not org_user:
        raise HTTPException(
            status_code=404,
            detail="Member not found in organization"
        )
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove yourself from the organization"
        )

    if org_user.role == OrganizationRole.ADMIN:
        admin_count = len(session.exec(
            select(OrganizationUser).where(
                OrganizationUser.organization_id == org_id,
                OrganizationUser.role == OrganizationRole.ADMIN
            )
        ).all())

        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last admin of the organization"
            )
        organization = session.get(Organization, org_id)
        user = session.get(User, user_id)
    try:
        session.delete(org_user)
        session.commit()

        background_tasks.add_task(
            email_service.send_member_remove_email,
            to_email=user.email,
            organization_name=organization.name
        )

        return {"message": "Member removed successfully"}

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error removing member: \n{str(e)} "
        )


@router.put("/{org_id}/members/change-role/{user_id}")
@require_permission(Permission.EDIT_ORGANIZATION)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    role_update: RoleUpdate,
    background_task: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):

    """
    Updates the role of an organization member and sends a notification email.

    Args:
        org_id (UUID): Organization identifier
        user_id (UUID): User identifier to update
        role_update (RoleUpdate): New role information
        background_task (BackgroundTasks): Task queue for email sending
        current_user (User): Authenticated user making the request
        session (Session): Database session

    Returns:
        dict: Message confirming role update with user ID and new role

    Raises:
        HTTPException: If member not found (404), self-modification attempted (400),or update fails (500)
    """
    # check if the members exists
    org_user = session.exec(
        select(OrganizationUser).where(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id
        )
    ).first()

    if not org_user:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevenir auto-modificación de rol
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify your own role"
        )

    try:
        organization = session.get(Organization, org_id)
        user = session.get(User, user_id)

        org_user.role = role_update.role
        session.add(org_user)
        session.commit()
        session.refresh(org_user)

        background_task.add_task(
            email_service.send_role_update_email,
            to_email=user.email,
            organization_name=organization.name,
            new_role=role_update.role
        )

        return {
            "message": "Role updated successfully",
            "user_id": str(user_id),
            "new_role": role_update.role
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error update role member: \n {str(e)}"
        )

@router.get("/{org_id}/settings", response_model=OrganizationSettings)
@require_permission(Permission.EDIT_ORGANIZATION)
async def get_organization_settings(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieves and formats organization settings with storage usage.

    Args:
        org_id: UUID of the organization
        current_user: Authenticated user from token
        session: Database session

    Returns:
        Dict containing organization settings with storage usage in GB

    Raises:
        HTTPException: If organization is not found
    """
    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    settings = dict(organization.settings)
    settings['storage']['used_gb'] = organization.storage_used / (1024 ** 3)

    return settings


@router.put("/{org_id}/settings", response_model=OrganizationSettings)
@require_permission(Permission.EDIT_ORGANIZATION)
async def update_organization_settings(
    org_id: UUID,
    settings_update: OrganizationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Updates organization settings for specified sections (security, notifications, storage).
    Validates storage limit against current usage and maintains existing settings.

    Args:
        org_id: UUID of the organization
        settings_update: Settings to update
        current_user: Authenticated user making the request
        session: Database session

    Returns:
        OrganizationSettings: Updated organization settings

    Raises:
        HTTPException: If organization not found (404) or storage limit below usage (400)
"""
    organization = session.get(Organization, org_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    if organization.settings is None:
        organization.settings = {}

    current_settings = dict(organization.settings)
    for section in ["security", "notifications", "storage"]:
        if section not in current_settings:
            current_settings[section] = {}

    storage_used_gb = organization.storage_used / (1024 * 1024 * 1024)

    update_dict = settings_update.dict(exclude_unset=True)
    for section, values in update_dict.items():
        if values:
            if section not in current_settings:
                current_settings[section] = {}
            current_settings[section].update(values)
    if (
        "storage" in update_dict and
        "limit_gb" in update_dict.get("storage", {}) and
        update_dict["storage"]["limit_gb"] < storage_used_gb
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot set storage limit below current usage"
        )

    
    organization.settings = current_settings
    session.add(organization)
    session.commit()
    session.refresh(organization)

    result_settings = dict(organization.settings)
    if "storage" not in result_settings:
        result_settings["storage"] = {}
    result_settings["storage"]["used_gb"] = storage_used_gb


    return OrganizationSettings(**result_settings)
