from typing import Optional
from sqlmodel import SQLModel
from .users import UserRead

class TokenResponse(SQLModel):
    access_token: str
    refresh_token: Optional[str]
    token_type: str = "bearer"
    user: UserRead

class LoginRequest(SQLModel):
    email: str
    password: str

class VerifyEmailRequest(SQLModel):
    email: str
    code: str

class RegisterResponse(SQLModel):
    message: str
    user: UserRead