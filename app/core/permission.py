from enum import Flag, auto
from functools import wraps
from fastapi import HTTPException,Depends
from sqlmodel import Session,select
from typing import Callable
from uuid import UUID
from ..core.security import get_current_user
from ..core.database import get_session
from ..models.organization import OrganizationUser, OrganizationRole

class Permission(Flag):
    NONE = 0
    VIEW_MEMBERS = auto()
    INVITE_MEMBERS = auto()
    REMOVE_MEMBERS = auto()
    EDIT_ORGANIZATION = auto()
    MANAGES_CONTRACT = auto()

ROLE_PERMISSIONS = {

    OrganizationRole.ADMIN : (
        Permission.VIEW_MEMBERS |
        Permission.INVITE_MEMBERS|
        Permission.REMOVE_MEMBERS |
        Permission.EDIT_ORGANIZATION |
        Permission.MANAGES_CONTRACT 
    ),
    OrganizationRole.EDITOR: (
        Permission.VIEW_MEMBERS | 
        Permission.MANAGES_CONTRACT
    ),
    OrganizationRole.VIEWER : (
        Permission.VIEW_MEMBERS
    )
}


def require_permission(permission: Permission):
    def decorator(func: Callable):  
        @wraps(func)
        async def wrapper (
            *args,
            org_id: UUID,
            current_user = Depends(get_current_user),
            session: Session = Depends(get_session),
            **kwargs
        ):
            org_user = session.exec(
                select(OrganizationUser).where(
                    OrganizationUser.user_id == current_user.id,
                    OrganizationUser.organization_id == org_id
                )
            ).first()

            if not org_user:
                raise HTTPException(status_code=404, detail="Not a member of this organization")

            if not (ROLE_PERMISSIONS[org_user.role] & permission):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
                
            return await func(*args, org_id=org_id, current_user=current_user, session=session, **kwargs)
        return wrapper
    return decorator