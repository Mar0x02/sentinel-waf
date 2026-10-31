from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_admin,
    get_or_create_jwt_secret,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models import Admin
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == payload.username).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(401, "Invalid username or password")
    secret = get_or_create_jwt_secret(db)
    token = create_access_token(admin.id, secret)
    return LoginResponse(access_token=token, must_change_password=admin.must_change_password)


@router.get("/me", response_model=MeResponse)
def me(admin: Admin = Depends(get_current_admin)):
    return MeResponse(username=admin.username, must_change_password=admin.must_change_password)


@router.post("/change-password", response_model=MeResponse)
def change_password(
    payload: ChangePasswordRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(401, "Current password is incorrect")
    admin.password_hash = hash_password(payload.new_password)
    admin.must_change_password = False
    db.commit()
    return MeResponse(username=admin.username, must_change_password=admin.must_change_password)
