from fastapi import APIRouter, Depends, HTTPException,Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from datetime import datetime

from ..core.security import get_current_user, redis_service
from ..models.users import User
from ..models.invitations import Invitation
from ..models.organization import OrganizationUser, Organization
from ..schemas.users import UserRead, UserUpdate
from ..schemas.invitations import InvitationAccept
from ..core.database import get_session, Session
from ..core.security import verify_password, get_password_hash


router = APIRouter()
security = HTTPBearer()

@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    response = current_user.dict()
    if current_user.organizations:
        org = current_user.current_organization
        response["organization"] = {
            "id": org.id,
            "name": org.name,
            "role": org.get_user_role(current_user.id),
            "total_members": org.total_members,
        }
    return response


@router.patch("/profile", response_model=UserRead)
async def update_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # Email validation
    if user_data.email and user_data.email != current_user.email:
        if session.exec(select(User).where(User.email == user_data.email)).first():
            raise HTTPException(status_code=400, detail="Email already registered")

    # Password validation       
    if user_data.current_password and user_data.new_password:        
        if not verify_password(user_data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect password")
        current_user.password_hash = get_password_hash(user_data.new_password)

    elif bool(user_data.current_password) != bool(user_data.new_password):
        raise HTTPException(
            status_code=400,
            detail="Both fields  are required to update password",
        )

    try:
        # Update fields excluding current_password and new_password
        update_data = user_data.dict(
            exclude={"current_password", "new_password"}, exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(current_user, field, value)

        # Refresh organization data if business user
        if not current_user.is_personal:
            session.refresh(current_user.current_organization)

        session.add(current_user)
        session.commit()
        return current_user
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
            detail="You're already a member of this organizabtion"
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

@router.get("/invitations/pending")
async def list_pending_invitations_by_email(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Buscar invitaciones usando el email del usuario actual
    invitations = session.exec(
        select(Invitation, Organization)
        .join(Organization)
        .where(
            Invitation.email == current_user.email,
            Invitation.expires_at > datetime.utcnow()
        )
    ).all()

    return {
        "invitations": [
            {
                "id": str(invitation.id),
                "organization": {
                    "id": str(organization.id),
                    "name": organization.name
                },
                "role": invitation.role,
                "token": invitation.token,
                "expires_at": invitation.expires_at
            }
            for invitation, organization in invitations
        ]
    }

@router.post('/logout')
async def logout(
    credentials: HTTPAuthorizationCredentials = Security(security),
    current_user: User = Depends(get_current_user)
):

    print(f"Logging out token: {credentials.credentials}")
    redis_service.add_to_blacklist(credentials.credentials, 1800)
    return{"message": "Logged out succesfully"}