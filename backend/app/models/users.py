from datetime import datetime
from typing import Optional, List
from  uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from .base import TimestampModel
from .types import AccountType

class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    account_type: AccountType = Field(default=AccountType.PERSONAL)



class User(UserBase, TimestampModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    password_hash: str = Field(min_length=4)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    verification_code: Optional[str] = Field(default=None, unique=True)
    verification_code_expires: Optional[datetime] = Field(default=None, unique=True)
    reset_password_token: Optional[str] = Field(default=None)
    reset_password_token_expires: Optional[datetime] = Field(default=None)

    # Relationships
    organizations: List["OrganizationUser"] = Relationship(back_populates="user")


    @property
    def is_personal(self) -> bool :
        return self.account_type == AccountType.PERSONAL

    @property
    def current_organization(self) -> Optional["Organization"]:
        return self.organizations[0].organization if self.organizations else None