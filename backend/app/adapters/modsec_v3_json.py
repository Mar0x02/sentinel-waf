import json
from datetime import datetime
from pathlib import Path

from app.schemas.logs import AuditLogEntry, RuleMatch

from .base import AuditLogParser

# ModSecurity v3 (libmodsecurity) JSON audit log, one JSON object per
# transaction. With SecAuditLogType Serial, multiple objects are appended to
# the same file separated by newlines (JSONL); some setups instead write one
# file per transaction. We handle both by scanning every file in the
# directory and parsing it either as JSONL or as a single JSON object.
_BLOCKING_HTTP_CODES = {403}


class ModSecV3JsonParser(AuditLogParser):
    def parse_dir(self, log_dir: Path) -> list[AuditLogEntry]:
        if not log_dir.exists():
            return []

        entries: list[AuditLogEntry] = []
        for path in sorted(log_dir.rglob("*")):
            if not path.is_file():
                continue
            entries.extend(self._parse_file(path))
        return entries

    def _parse_file(self, path: Path) -> list[AuditLogEntry]:
        raw = path.read_text(errors="replace").strip()
        if not raw:
            return []

        objects: list[dict] = []
        try:
            # Single JSON object (one-file-per-transaction layout).
            objects = [json.loads(raw)]
        except json.JSONDecodeError:
            # JSONL: one object per line. Skip lines that don't parse -
            # a log file being written to while we read it can have a
            # trailing partial line.
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    objects.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        entries = []
        for obj in objects:
            entry = self._to_entry(obj)
            if entry is not None:
                entries.append(entry)
        return entries

    def _to_entry(self, obj: dict) -> AuditLogEntry | None:
        tx = obj.get("transaction")
        if not isinstance(tx, dict):
            return None

        # "unique_id" is what ModSecurity v3 actually emits (verified against
        # a real owasp/modsecurity-crs:nginx container); the other two keys
        # are kept as fallbacks in case a different connector/version uses
        # them instead.
        transaction_id = tx.get("unique_id") or tx.get("transaction_id") or tx.get("id")
        if not transaction_id:
            return None

        timestamp = self._parse_timestamp(tx.get("time_stamp"))

        request = tx.get("request") or {}
        response = tx.get("response") or {}
        status_code = response.get("http_code")
        headers = request.get("headers") or {}
        user_agent = self._header(headers, "user-agent")
        host = request.get("hostname") or self._header(headers, "host")

        matches = [
            match
            for match in (self._to_match(m) for m in tx.get("messages") or [])
            if match is not None
        ]

        blocked = status_code in _BLOCKING_HTTP_CODES or any(
            m.severity in ("0", "1", "CRITICAL") for m in matches
        )

        return AuditLogEntry(
            transaction_id=transaction_id,
            timestamp=timestamp,
            client_ip=tx.get("client_ip"),
            host=host,
            user_agent=user_agent,
            method=request.get("method"),
            uri=request.get("uri"),
            status_code=status_code,
            blocked=blocked,
            matches=matches,
        )

    @staticmethod
    def _header(headers: dict, name: str) -> str | None:
        # Header key casing isn't guaranteed (clients send "User-Agent",
        # "user-agent", etc.) - match case-insensitively.
        name = name.lower()
        for key, value in headers.items():
            if isinstance(key, str) and key.lower() == name:
                return value
        return None

    @staticmethod
    def _to_match(raw: dict) -> RuleMatch | None:
        if not isinstance(raw, dict):
            return None
        details = raw.get("details") or {}
        return RuleMatch(
            rule_id=str(details.get("ruleId")) if details.get("ruleId") else None,
            message=raw.get("message") or details.get("msg"),
            severity=str(details.get("severity")) if details.get("severity") is not None else None,
            tags=details.get("tags") or [],
            data=details.get("data"),
        )

    @staticmethod
    def _parse_timestamp(raw: str | None) -> datetime | None:
        if not raw:
            return None
        # ModSecurity's default time_stamp format: "Mon Jan 02 15:04:05 2006"
        for fmt in ("%a %b %d %H:%M:%S %Y", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None
