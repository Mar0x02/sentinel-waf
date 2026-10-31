from pathlib import Path

from app.schemas.logs import AuditLogEntry

from .base import AuditLogParser
from .modsec_v3_json import ModSecV3JsonParser

_PARSERS: dict[str, type[AuditLogParser]] = {
    "modsec_v3_json": ModSecV3JsonParser,
}


def get_log_parser(format_name: str) -> AuditLogParser:
    """Factory for audit log parsers, keyed by WAF_AUDIT_LOG_FORMAT.

    Add new WAF backends (e.g. Apache + mod_security2 native format) by
    implementing AuditLogParser and registering it here - nothing else in
    the app needs to change.
    """
    try:
        parser_cls = _PARSERS[format_name]
    except KeyError:
        raise ValueError(
            f"Unknown audit log format '{format_name}'. "
            f"Available: {', '.join(_PARSERS)}"
        )
    return parser_cls()


__all__ = ["AuditLogParser", "AuditLogEntry", "get_log_parser"]
