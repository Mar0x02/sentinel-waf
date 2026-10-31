from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_admin_role
from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.engine_settings import EngineSettingsOut, EngineSettingsUpdate
from app.services import render_service

router = APIRouter(prefix="/api/engine-settings", tags=["engine-settings"])


@router.get("", response_model=EngineSettingsOut)
def get_engine_settings(db: Session = Depends(get_db)):
    return render_service.get_or_create_engine_settings(db)


@router.put("", response_model=EngineSettingsOut, dependencies=[Depends(require_admin_role)])
def update_engine_settings(
    payload: EngineSettingsUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    row = render_service.get_or_create_engine_settings(db)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    render_service.render_engine_settings(db, settings)
    return row
