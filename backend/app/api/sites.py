from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_write_access
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Site
from app.schemas.sites import AntiBotUpdate, EnabledPatch, SiteCreate, SiteOut, SiteUpdate
from app.services import render_service
from app.services.tls_service import expiry_from_pem

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _site_out(site: Site) -> SiteOut:
    return SiteOut(
        id=site.id,
        name=site.name,
        domain=site.domain,
        upstream_url=site.upstream_url,
        listen_port=site.listen_port,
        enabled=site.enabled,
        created_at=site.created_at,
        updated_at=site.updated_at,
        tls_enabled=site.tls_enabled,
        tls_listen_port=site.tls_listen_port,
        has_cert=bool(site.tls_cert),
        cert_expires_at=expiry_from_pem(site.tls_cert) if site.tls_cert else None,
        rate_limit_enabled=site.rate_limit_enabled,
        rate_limit_rps=site.rate_limit_rps,
        rate_limit_burst=site.rate_limit_burst,
        conn_limit_enabled=site.conn_limit_enabled,
        conn_limit_per_ip=site.conn_limit_per_ip,
        bot_challenge_enabled=site.bot_challenge_enabled,
        honeypot_checkbox_enabled=site.honeypot_checkbox_enabled,
        honeypot_path_enabled=site.honeypot_path_enabled,
        block_bad_user_agents=site.block_bad_user_agents,
    )


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return [_site_out(s) for s in db.query(Site).order_by(Site.id).all()]


@router.post("", response_model=SiteOut, status_code=201)
def create_site(
    payload: SiteCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    site = Site(**payload.model_dump())
    db.add(site)
    db.commit()
    render_service.render_sites(db, settings)
    return _site_out(site)


@router.put("/{site_id}", response_model=SiteOut)
def update_site(
    site_id: int,
    payload: SiteUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")

    data = payload.model_dump()
    # tls_cert/tls_key omitted (None) means "leave the stored cert alone" -
    # the frontend never re-sends the private key it was never given back
    # in the first place (see SiteOut). Only overwrite both when a new pair
    # was actually uploaded (already validated as a matching pair by
    # SiteUpdate's model_validator).
    new_cert, new_key = data.pop("tls_cert"), data.pop("tls_key")
    for key, value in data.items():
        setattr(site, key, value)
    if new_cert is not None:
        site.tls_cert = new_cert
        site.tls_key = new_key

    if site.tls_enabled and not site.tls_cert:
        raise HTTPException(422, "tls_cert and tls_key are required to enable HTTPS")

    db.commit()
    render_service.render_sites(db, settings)
    return _site_out(site)


@router.patch("/{site_id}", response_model=SiteOut)
def toggle_site(
    site_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    site.enabled = payload.enabled
    db.commit()
    render_service.render_sites(db, settings)
    return _site_out(site)


@router.patch("/{site_id}/anti-bot", response_model=SiteOut)
def update_anti_bot(
    site_id: int,
    payload: AntiBotUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    for key, value in payload.model_dump().items():
        setattr(site, key, value)
    db.commit()
    render_service.render_sites(db, settings)
    return _site_out(site)


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(404, "Site not found")
    db.delete(site)
    db.commit()
    render_service.render_sites(db, settings)
