from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta


from ..models.users import User
from ..models.organization import Organization, OrganizationUser, OrganizationRole

from ..schemas.auth import (
    TokenResponse,RegisterResponse,VerifyEmailRequest,LoginRequest
)

from ..schemas.users import UserCreate
from ..core.database import get_session, get_settings
from ..core.security import create_access_token,create_refresh_token,get_password_hash,verify_password

from ..services.email_services import email_service


router  = APIRouter()
settings = get_settings()

@router.post("/register", response_model=RegisterResponse)
async def register ( background_tasks: BackgroundTasks, user_data: UserCreate, session: Session = Depends(get_session)):

    if session.exec(select(User).where(User.email == user_data.email)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Email already registed'
        )
    
    try:
        verification_code = email_service.generate_verification_code()
        expires = datetime.utcnow() + timedelta(hours=settings.VERIFICATION_CODE_EXPIRE_HOUR)
        user = User(
            email=user_data.email,
            password_hash = get_password_hash(user_data.password),
            full_name = user_data.full_name,
            account_type = user_data.account_type,
            verification_code = verification_code,
            verification_code_expires = expires
        )
        session.add(user)
        session.flush()

        if not user.is_personal:
            if not user_data.organization_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization name is required for business accounts"
                )
            organization = Organization(name=user_data.organizations)
            session.add(organization)
            session.flush()

            org_user = OrganizationUser(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.ADMIN
            )
            session.add(org_user)
       

        background_tasks.add_task(
            email_service.send_verification_email,
            user.email,
            verification_code
        )
        session.commit()
        session.refresh(user)

        return RegisterResponse(
            user=user,
            message="Registration successful. Please check your email to verify your account."
            
        )

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

