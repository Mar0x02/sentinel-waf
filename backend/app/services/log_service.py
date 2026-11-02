from app.adapters import get_log_parser
from app.config import Settings
from app.schemas.logs import AuditLogEntry, AuditLogPage
from app.services.attack_categories import match_category


def load_entries(settings: Settings) -> list[AuditLogEntry]:
    parser = get_log_parser(settings.audit_log_format)
    entries = parser.parse_dir(settings.audit_log_dir)
    return sorted(entries, key=lambda e: e.timestamp or e.transaction_id, reverse=True)


def query_entries(
    settings: Settings,
    *,
    limit: int = 50,
    offset: int = 0,
    severity: str | None = None,
    rule_id: str | None = None,
    client_ip: str | None = None,
    category: str | None = None,
    blocked_only: bool = False,
) -> AuditLogPage:
    entries = load_entries(settings)

    if severity:
        entries = [e for e in entries if any(m.severity == severity for m in e.matches)]
    if rule_id:
        entries = [e for e in entries if any(m.rule_id == rule_id for m in e.matches)]
    if client_ip:
        entries = [e for e in entries if e.client_ip == client_ip]
    if category:
        entries = [e for e in entries if any(category in match_category(m.tags) for m in e.matches)]
    if blocked_only:
        entries = [e for e in entries if e.blocked]

    total = len(entries)
    page = entries[offset : offset + limit]
    return AuditLogPage(total=total, limit=limit, offset=offset, items=page)


def get_entry(settings: Settings, transaction_id: str) -> AuditLogEntry | None:
    for entry in load_entries(settings):
        if entry.transaction_id == transaction_id:
            return entry
    return None
