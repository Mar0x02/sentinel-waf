from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import hash_password, reset_user_password, require_admin_role
from app.db import get_db
from app.models import Role, User
from app.schemas.users import UserCreate, UserOut, UserResetPasswordResponse, UserUpdateRole

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin_role)])


def _admin_count(db: Session, exclude_id: int | None = None) -> int:
    query = db.query(User).filter(User.role == Role.admin)
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    return query.count()


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(409, f"Username '{payload.username}' is already taken")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: int,
    payload: UserUpdateRole,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_role),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.role == Role.admin and payload.role != Role.admin and _admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(400, "Can't remove the last admin - promote someone else first")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserResetPasswordResponse)
def reset_password(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    new_password = reset_user_password(db, user.username)
    assert new_password is not None
    return UserResetPasswordResponse(username=user.username, new_password=new_password)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_admin_role),
):
    if user_id == current.id:
        raise HTTPException(400, "You can't delete your own account")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.role == Role.admin and _admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(400, "Can't delete the last admin - promote someone else first")
    db.delete(user)
    db.commit()
