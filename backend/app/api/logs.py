from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.schemas.logs import AuditLogEntry, AuditLogPage
from app.services import log_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=AuditLogPage)
def list_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity: str | None = None,
    rule_id: str | None = None,
    client_ip: str | None = None,
    category: str | None = None,
    blocked_only: bool = False,
    settings: Settings = Depends(get_settings),
):
    return log_service.query_entries(
        settings,
        limit=limit,
        offset=offset,
        severity=severity,
        rule_id=rule_id,
        client_ip=client_ip,
        category=category,
        blocked_only=blocked_only,
    )


@router.get("/{transaction_id}", response_model=AuditLogEntry)
def get_log(transaction_id: str, settings: Settings = Depends(get_settings)):
    entry = log_service.get_entry(settings, transaction_id)
    if entry is None:
        raise HTTPException(404, f"Transaction '{transaction_id}' not found")
    return entry
