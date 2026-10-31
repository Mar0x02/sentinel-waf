from pydantic import BaseModel, Field

from app.models import Role


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    must_change_password: bool
    role: Role


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class MeResponse(BaseModel):
    username: str
    role: Role
    must_change_password: bool
