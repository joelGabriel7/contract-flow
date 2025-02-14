from fastapi import APIRouter, Depends
from ..core.security import get_current_user
from ..models.users import User
from ..schemas.users import UserRead


router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user:User = Depends(get_current_user)):

    response =  current_user.dict()
    if not current_user.is_personal:
        org = current_user.current_organization
        response["organization"] = {
                "id": org.id,
                "name": org.name,
                "role": org.get_user_role(current_user.id),
                "total_members": org.total_members
            }
    return response