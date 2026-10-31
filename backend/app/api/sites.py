from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Site
from app.schemas.sites import EnabledPatch, SiteCreate, SiteOut, SiteUpdate
from app.services import render_service

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(Site).order_by(Site.id).all()


@router.post("", response_model=SiteOut, status_code=201)
def create_site(payload: SiteCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    site = Site(**payload.model_dump())
    db.add(site)
    db.commit()
    render_service.render_sites(db, settings)
    return site


@router.put("/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    payload: SiteUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    for key, value in payload.model_dump().items():
        setattr(site, key, value)
    db.commit()
    render_service.render_sites(db, settings)
    return site


@router.patch("/{site_id}", response_model=SiteOut)
def toggle_site(
    site_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    site.enabled = payload.enabled
    db.commit()
    render_service.render_sites(db, settings)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    db.delete(site)
    db.commit()
    render_service.render_sites(db, settings)
