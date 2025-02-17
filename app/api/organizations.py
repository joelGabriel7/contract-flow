from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from uuid import UUID
from typing import List

from ..core.permission import require_permission, Permission
from ..core.security import get_current_user, get_session
from ..schemas.organization import AdminDashboardResponse
from ..schemas.invitations import InvitationResponse, InvitationCreate, InvitationAccept
from ..models.users import User
from ..models.invitations import Invitation
from ..models.organization import Organization, OrganizationUser
from ..services.email_services import email_service

import secrets
from datetime import datetime, timedelta



router = APIRouter()

# @router.get("/{org_id}/dashboard", response_model=AdminDashboardResponse)
# @require_permission(Permission.EDIT_ORGANIZATION)
# async def admin_dashboard(
#     org_id: UUID,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session)
# ):

#     organization = session.get(Organization, org_id) 
#     if not organization:
#         raise HTTPException(status_code=404, detail="Organization not found")

#     members_query = select(OrganizationUser, User).join(
#         User, OrganizationUser.user_id == User.id
#     ).where(OrganizationUser.organization_id == org_id)
    
#     members  = session.exec(memoryview).all()


#     total_members = len(members)
#     members_by_role = {}
#     for org_user, _ in members:
#         role = org_user.role
#         members_by_role[role] = members_by_role.get(role, 0) + 1

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

    # Enviar email en segundo plano
    background_tasks.add_task(
        email_service.send_invitation_email,
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
            id= invitation.id,
            email= invitation.email,
            role = invitation.role,
            expires_at = invitation.expires_at,
            organization_name=organization.name
            
        ) for invitation in invitations
    ]

@router.post('/invitations/accept')
async def accept_invitation(
    invitation_data: InvitationAccept,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    invitation = session.exec(
        select(Invitation).where(
            Invitation.token == invitation_data.token,
            Invitation.expires_at > datetime.utcnow()
        )
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=404,
            detail='Invalid or expired invitation'
        )
    
    if current_user.email != invitation.email:
        raise HTTPException(
            status_code=403,
            detail="This invitations was sent to a different email"
        )
    organization = session.get(Organization, invitation.organization_id)
    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Organization not found"
        )
    existing_member = session.exec(
        select(OrganizationUser).where(
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.organization_id == invitation.id,
        )
    ).first()

    if existing_member:
        session.delete(invitation)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail="You're already a member of this organization"
        )


    try:
        new_member = OrganizationUser(
            organization_id=invitation.organization_id,
            user_id = current_user.id,
            role=invitation.role
        )
        session.add(new_member)
        session.delete(invitation)
        session.commit()

        return {
            "message": "Invitation accepted successfully",
            "organization_id": str(invitation.organization_id),
            "role": invitation.role
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error accepting invitations: {str(e)}"
        )