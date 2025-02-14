from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta


from ..models.users import User
from ..models.organization import Organization, OrganizationUser, OrganizationRole

from ..schemas.auth import (
    TokenResponse,
    RegisterResponse,
    VerifyEmailRequest,
    LoginRequest,
    ResetPassword,
)

from ..schemas.users import UserCreate
from ..core.database import get_session, get_settings
from ..core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)

from ..services.email_services import email_service


router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=RegisterResponse)
async def register(
    background_tasks: BackgroundTasks,
    user_data: UserCreate,
    session: Session = Depends(get_session),
):
    if session.exec(select(User).where(User.email == user_data.email)).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registed"
        )
    verification_code = email_service.generate_verification_code()
    expires = datetime.utcnow() + timedelta(
        hours=settings.VERIFICATION_CODE_EXPIRE_HOUR
    )
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        account_type=user_data.account_type,
        verification_code=verification_code,
        verification_code_expires=expires,
    )
    session.add(user)
    session.flush()

    if not user.is_personal:
        if not user_data.organizations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name is required for business accounts",
            )
        organization = Organization(name=user_data.organizations)
        session.add(organization)
        session.flush()

        org_user = OrganizationUser(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ADMIN,
        )
        session.add(org_user)

    try:
        background_tasks.add_task(
            email_service.send_verification_email, user.email, verification_code
        )
        session.commit()
        session.refresh(user)

        return RegisterResponse(
            user=user,
            message="Registration successful. Please check your email to verify your account.",
        )

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/verify-email")
async def verify_email(
    verify_data: VerifyEmailRequest, session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.email == verify_data.email)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found, please sign up",
        )
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified"
        )

    if not user.verification_code or not user.verification_code_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No verification code found"
        )

    if datetime.utcnow() > user.verification_code_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired",
        )

    if user.verification_code != verify_data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code"
        )

    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires = None

    session.add(user)
    session.commit()

    return {"message": "Email verified successfully"}


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == login_data.email)).first()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please verify your email before logging in",
        )

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user,
    )


@router.post("/resend-verification")
async def resend_verification(
    background_task: BackgroundTasks,
    email: str,
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        print("Entro here")
        return {
            "message": "If the email exits and is not verified, you will receive a new code"
        }

    verification_code = email_service.generate_verification_code()
    expires = datetime.utcnow() + timedelta(
        hours=settings.VERIFICATION_CODE_EXPIRE_HOUR
    )

    user.verification_code = verification_code
    user.verification_code_expires = expires

    background_task.add_task(
        email_service.send_verification_email, email, verification_code
    )
    session.commit()
    return {
        "message": "If the email exists and is not verified, you will receive a new code"
    }


@router.post("/forgot-password")
async def forgot_password(
    background_task: BackgroundTasks,
    email: str,
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return {"message": "If account exists, you'll receive reset code"}

    reset_code = email_service.generate_verification_code()
    expires = datetime.utcnow() + timedelta(
        hours=settings.VERIFICATION_CODE_EXPIRE_HOUR
    )

    user.reset_password_token = reset_code
    user.reset_password_token_expires = expires

    background_task.add_task(email_service.send_reset_password_email, email, reset_code)
    session.commit()

    return {"message": "You'll receive a reset code"}


@router.post("/reset-password")
async def reset_password(
    reset_body: ResetPassword, session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.email == reset_body.email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not user.reset_password_token or not user.reset_password_token_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Token"
        )
    if (
        datetime.utcnow() > user.reset_password_token_expires
        or user.reset_password_token != reset_body.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Expire Token"
        )
    if reset_body.new_password != reset_body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords must to match"
        )
    try:
        user.password_hash = get_password_hash(reset_body.new_password)
        user.reset_password_token = None
        user.reset_password_token_expires = None

        session.commit()
        return {"message": "Password updated succesfully"}

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
