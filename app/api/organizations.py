from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from uuid import UUID
from typing import List

from ..core.permission import require_permission, Permission
from ..core.security import get_current_user, get_session
from ..schemas.organization import AdminDashboardResponse, OrganizationRead, DashboardMemberInfo, DashboardMetrics, RoleUpdate
from ..schemas.invitations import InvitationResponse, InvitationCreate
from ..models.users import User
from ..models.invitations import Invitation
from ..models.organization import Organization, OrganizationUser, OrganizationRole
from ..services.email_services import email_service

import secrets
from datetime import datetime, timedelta


router = APIRouter()


@router.get("/{org_id}/dashboard", response_model=AdminDashboardResponse)
@require_permission(Permission.EDIT_ORGANIZATION)
async def admin_dashboard(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):

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
