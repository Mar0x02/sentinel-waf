from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_or_create_jwt_secret,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    secret = get_or_create_jwt_secret(db)
    token = create_access_token(user.id, secret)
    return LoginResponse(access_token=token, must_change_password=user.must_change_password, role=user.role)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(username=user.username, role=user.role, must_change_password=user.must_change_password)


@router.post("/change-password", response_model=MeResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    return MeResponse(username=user.username, role=user.role, must_change_password=user.must_change_password)
