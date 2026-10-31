import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Admin, AppSecret

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


def create_access_token(admin_id: int, secret: str) -> str:
    payload = {"sub": str(admin_id), "exp": datetime.now(timezone.utc) + TOKEN_TTL}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def ensure_admin_seeded(db: Session) -> None:
    """Creates the one admin account on first boot with a random password,
    printed to the container logs - there is no other way to retrieve it
    (it's never stored in plaintext). Does nothing on later boots.
    """
    if db.query(Admin).first() is not None:
        return
    password = secrets.token_urlsafe(16)
    admin = Admin(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=hash_password(password),
        must_change_password=True,
    )
    db.add(admin)
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


def get_current_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Admin:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    secret = get_or_create_jwt_secret(db)
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")
    admin = db.get(Admin, int(payload["sub"]))
    if admin is None:
        raise HTTPException(401, "Invalid or expired session")
    return admin
