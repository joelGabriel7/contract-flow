from fastapi import APIRouter, Depends
from ..core.security import get_current_user
from ..models.users import User
from ..schemas.users import UserRead


router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_current_user_info(current_user:User = Depends(get_current_user)):
    return current_user