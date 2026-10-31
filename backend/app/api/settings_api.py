from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import LogSink
from app.schemas.settings import EnabledPatch, LogSinkCreate, LogSinkOut, LogSinkUpdate
from app.services import render_service

router = APIRouter(prefix="/api/log-sinks", tags=["settings"])


@router.get("", response_model=list[LogSinkOut])
def list_log_sinks(db: Session = Depends(get_db)):
    return db.query(LogSink).order_by(LogSink.id).all()


@router.post("", response_model=LogSinkOut, status_code=201)
def create_log_sink(
    payload: LogSinkCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    sink = LogSink(**payload.model_dump())
    db.add(sink)
    db.commit()
    render_service.render_log_sinks(db, settings)
    return sink


@router.put("/{sink_id}", response_model=LogSinkOut)
def update_log_sink(
    sink_id: int,
    payload: LogSinkUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    sink = db.get(LogSink, sink_id)
    if sink is None:
        raise HTTPException(404, "Log sink not found")
    for key, value in payload.model_dump().items():
        setattr(sink, key, value)
    db.commit()
    render_service.render_log_sinks(db, settings)
    return sink


@router.patch("/{sink_id}", response_model=LogSinkOut)
def toggle_log_sink(
    sink_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    sink = db.get(LogSink, sink_id)
    if sink is None:
        raise HTTPException(404, "Log sink not found")
    sink.enabled = payload.enabled
    db.commit()
    render_service.render_log_sinks(db, settings)
    return sink


@router.delete("/{sink_id}", status_code=204)
def delete_log_sink(sink_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    sink = db.get(LogSink, sink_id)
    if sink is None:
        raise HTTPException(404, "Log sink not found")
    db.delete(sink)
    db.commit()
    render_service.render_log_sinks(db, settings)
