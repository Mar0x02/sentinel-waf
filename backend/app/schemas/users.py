from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Role


class UserOut(BaseModel):
    id: int
    username: str
    role: Role
    must_change_password: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=8)
    role: Role = Role.viewer


class UserUpdateRole(BaseModel):
    role: Role


class UserResetPasswordResponse(BaseModel):
    username: str
    new_password: str
