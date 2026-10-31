from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.logs import AuditLogEntry


class AuditLogParser(ABC):
    """Turns a WAF's raw audit log directory into AuditLogEntry objects.

    Each supported WAF engine/log format gets its own implementation so the
    rest of the app (services, API) never deals with raw log formats.
    """

    @abstractmethod
    def parse_dir(self, log_dir: Path) -> list[AuditLogEntry]:
        ...
