from fastapi import APIRouter, Depends, HTTPException
from ..core.security import get_current_user
from ..models.users import User
from ..schemas.users import UserRead, UserUpdate
from ..core.database import get_session, Session
from ..core.security import verify_password, get_password_hash
from sqlmodel import select


router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    response = current_user.dict()
    if not current_user.is_personal:
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
