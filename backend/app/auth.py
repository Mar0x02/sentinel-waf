import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AppSecret, Role, User

JWT_SECRET_KEY_NAME = "jwt_secret"
JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)
DEFAULT_ADMIN_USERNAME = "admin"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def get_or_create_jwt_secret(db: Session) -> str:
    row = db.get(AppSecret, JWT_SECRET_KEY_NAME)
    if row is None:
        row = AppSecret(key=JWT_SECRET_KEY_NAME, value=secrets.token_hex(32))
        db.add(row)
        db.commit()
    return row.value


def create_access_token(user_id: int, secret: str) -> str:
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + TOKEN_TTL}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def rotate_jwt_secret(db: Session) -> None:
    """Invalidates every outstanding session token immediately by replacing
    the signing key - used by the reset-password CLI so a reset (e.g.
    because a password may have leaked) also kicks out anyone already
    logged in, not just the account owner.
    """
    row = db.get(AppSecret, JWT_SECRET_KEY_NAME)
    if row is None:
        row = AppSecret(key=JWT_SECRET_KEY_NAME, value=secrets.token_hex(32))
        db.add(row)
    else:
        row.value = secrets.token_hex(32)
    db.commit()


def ensure_admin_seeded(db: Session) -> None:
    """Creates the first user (role=admin) on first boot with a random
    password, printed to the container logs - there is no other way to
    retrieve it (it's never stored in plaintext). Does nothing once any
    user exists, including ones created later via the Team page.
    """
    if db.query(User).first() is not None:
        return
    password = secrets.token_urlsafe(16)
    user = User(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=hash_password(password),
        role=Role.admin,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    print(
        "\n"
        "==================================================================\n"
        "  Sentinel WAF - initial admin account created\n"
        f"  username: {DEFAULT_ADMIN_USERNAME}\n"
        f"  password: {password}\n"
        "  This password is shown ONLY this one time - it is not stored in\n"
        "  plaintext anywhere. Log in and change it from the dashboard.\n"
        "==================================================================\n",
        flush=True,
    )


def reset_user_password(db: Session, username: str) -> str | None:
    """Generates a new random password for the given username and forces a
    change on next login. Returns the new password, or None if that
    username doesn't exist. Also rotates the JWT secret, signing out every
    active session - see rotate_jwt_secret().
    """
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        return None
    new_password = secrets.token_urlsafe(16)
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    db.commit()
    rotate_jwt_secret(db)
    return new_password


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    secret = get_or_create_jwt_secret(db)
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(401, "Invalid or expired session")
    return user


def require_role(*roles: Role):
    """Dependency factory: raises 403 unless the current user's role is one
    of `roles`. Applied per-endpoint (not per-router) wherever a write
    needs a higher bar than "logged in" - see CLAUDE.md for why routers
    can't just do this once at include_router() time like the plain
    logged-in check does.
    """

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have permission to do this")
        return user

    return checker


require_write_access = require_role(Role.admin, Role.operator)
require_admin_role = require_role(Role.admin)
