from datetime import datetime

from pydantic import BaseModel


class RuleMatch(BaseModel):
    rule_id: str | None = None
    message: str | None = None
    severity: str | None = None
    tags: list[str] = []
    data: str | None = None


class AuditLogEntry(BaseModel):
    transaction_id: str
    timestamp: datetime | None = None
    client_ip: str | None = None
    host: str | None = None
    user_agent: str | None = None
    method: str | None = None
    uri: str | None = None
    status_code: int | None = None
    blocked: bool = False
    matches: list[RuleMatch] = []
    headers: dict[str, str] = {}


class AuditLogPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogEntry]
