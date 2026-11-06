from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_write_access
from app.config import Settings, get_settings
from app.db import get_db
from app.models import IpRule
from app.schemas.ip_rules import EnabledPatch, IpRuleCreate, IpRuleOut
from app.services import render_service

router = APIRouter(prefix="/api/ip-rules", tags=["ip-rules"])


@router.get("", response_model=list[IpRuleOut])
def list_ip_rules(db: Session = Depends(get_db)):
    return db.query(IpRule).order_by(IpRule.id).all()


@router.post("", response_model=IpRuleOut, status_code=201)
def create_ip_rule(
    payload: IpRuleCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    if db.query(IpRule).filter(IpRule.ip == payload.ip).first():
        raise HTTPException(409, f"'{payload.ip}' is already on a list")
    rule = IpRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    render_service.render_ip_rules(db, settings)
    return rule


@router.patch("/{rule_id}", response_model=IpRuleOut)
def toggle_ip_rule(
    rule_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    rule = db.get(IpRule, rule_id)
    if rule is None:
        raise HTTPException(404, "IP rule not found")
    rule.enabled = payload.enabled
    db.commit()
    render_service.render_ip_rules(db, settings)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_ip_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    rule = db.get(IpRule, rule_id)
    if rule is None:
        raise HTTPException(404, "IP rule not found")
    db.delete(rule)
    db.commit()
    render_service.render_ip_rules(db, settings)
