from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_or_create_jwt_secret,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.login_lockout import record_failure, record_success, seconds_until_unlocked
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # X-Real-IP is only trustworthy because the sole path to this backend
    # in production is through frontend's own nginx (frontend/nginx.prod.conf
    # sets it; the backend container has no host port at all in that mode -
    # see docker-compose.prod.yml). In dev mode nothing sets this header
    # (the frontend calls the backend's exposed port directly), so this
    # falls back to the direct peer address, which is the real client there.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    locked_for = seconds_until_unlocked(ip)
    if locked_for > 0:
        retry_after = int(locked_for) + 1
        raise HTTPException(
            429,
            f"Too many failed login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        record_failure(ip)
        raise HTTPException(401, "Invalid username or password")

    record_success(ip)
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
