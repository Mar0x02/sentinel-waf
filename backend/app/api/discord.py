from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin_role
from app.config import Settings, get_settings
from app.db import get_db
from app.models import DiscordWebhook
from app.schemas.discord import DiscordWebhookCreate, DiscordWebhookOut, DiscordWebhookUpdate, EnabledPatch
from app.services import render_service

router = APIRouter(prefix="/api/discord-webhooks", tags=["discord"])


@router.get("", response_model=list[DiscordWebhookOut])
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(DiscordWebhook).order_by(DiscordWebhook.id).all()


@router.post("", response_model=DiscordWebhookOut, status_code=201, dependencies=[Depends(require_admin_role)])
def create_webhook(
    payload: DiscordWebhookCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    webhook = DiscordWebhook(**payload.model_dump())
    db.add(webhook)
    db.commit()
    render_service.render_discord_webhooks(db, settings)
    return webhook


@router.put("/{webhook_id}", response_model=DiscordWebhookOut, dependencies=[Depends(require_admin_role)])
def update_webhook(
    webhook_id: int,
    payload: DiscordWebhookUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    webhook = db.get(DiscordWebhook, webhook_id)
    if webhook is None:
        raise HTTPException(404, "Webhook not found")
    for key, value in payload.model_dump().items():
        setattr(webhook, key, value)
    db.commit()
    render_service.render_discord_webhooks(db, settings)
    return webhook


@router.patch("/{webhook_id}", response_model=DiscordWebhookOut, dependencies=[Depends(require_admin_role)])
def toggle_webhook(
    webhook_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    webhook = db.get(DiscordWebhook, webhook_id)
    if webhook is None:
        raise HTTPException(404, "Webhook not found")
    webhook.enabled = payload.enabled
    db.commit()
    render_service.render_discord_webhooks(db, settings)
    return webhook


@router.delete("/{webhook_id}", status_code=204, dependencies=[Depends(require_admin_role)])
def delete_webhook(webhook_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    webhook = db.get(DiscordWebhook, webhook_id)
    if webhook is None:
        raise HTTPException(404, "Webhook not found")
    db.delete(webhook)
    db.commit()
    render_service.render_discord_webhooks(db, settings)
