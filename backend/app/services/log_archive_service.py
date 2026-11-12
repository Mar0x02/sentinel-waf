"""Reads/deletes the gzip-archived audit log chunks waf-engine's
docker-entrypoint.d/03-audit-log-rotate.sh writes under
Settings.audit_log_archive_dir, one subfolder per calendar day
(YYYY-MM-DD) holding audit-<start>_<end>.gz chunks. Pure filesystem
browsing - no DB table, the day folders and filenames are the source of
truth, same as every other rendered-volume reader in this project.
"""

import gzip
import re
from pathlib import Path

from app.config import Settings
from app.schemas.logs import ArchiveDate, ArchiveFile

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Matches exactly what the rotate script creates - audit-HHMMSS_HHMMSS.gz.
# Anything that doesn't match this is never touched by list/delete/download,
# so a date or filename coming straight off a URL path segment can't be
# used for path traversal (same guard class as custom rule filenames -
# see CLAUDE.md's "Security boundaries" section).
_FILENAME_RE = re.compile(r"^audit-(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.gz$")


def _resolve_file(settings: Settings, date: str, filename: str) -> Path:
    if not _DATE_RE.match(date) or not _FILENAME_RE.match(filename):
        raise ValueError("invalid date or filename")
    root = settings.audit_log_archive_dir.resolve()
    path = (root / date / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError("invalid path")
    return path


def list_dates(settings: Settings) -> list[ArchiveDate]:
    root = settings.audit_log_archive_dir
    if not root.exists():
        return []
    out = []
    for day_dir in sorted(root.iterdir(), reverse=True):
        if not day_dir.is_dir() or not _DATE_RE.match(day_dir.name):
            continue
        files = [f for f in day_dir.iterdir() if f.is_file() and _FILENAME_RE.match(f.name)]
        if not files:
            continue
        out.append(
            ArchiveDate(
                date=day_dir.name,
                file_count=len(files),
                total_size_bytes=sum(f.stat().st_size for f in files),
            )
        )
    return out


def list_files(settings: Settings, date: str) -> list[ArchiveFile]:
    if not _DATE_RE.match(date):
        raise ValueError("invalid date")
    day_dir = settings.audit_log_archive_dir / date
    if not day_dir.exists():
        return []
    out = []
    for f in sorted(day_dir.iterdir()):
        m = _FILENAME_RE.match(f.name)
        if not f.is_file() or not m:
            continue
        out.append(
            ArchiveFile(
                filename=f.name,
                start_time=f"{m.group(1)}:{m.group(2)}:{m.group(3)}",
                end_time=f"{m.group(4)}:{m.group(5)}:{m.group(6)}",
                size_bytes=f.stat().st_size,
            )
        )
    return out


def delete_file(settings: Settings, date: str, filename: str) -> bool:
    path = _resolve_file(settings, date, filename)
    if not path.exists():
        return False
    path.unlink()
    return True


def read_gz_bytes(settings: Settings, date: str, filename: str) -> bytes:
    path = _resolve_file(settings, date, filename)
    if not path.exists():
        raise FileNotFoundError(filename)
    return path.read_bytes()


def read_decompressed(settings: Settings, date: str, filename: str) -> bytes:
    return gzip.decompress(read_gz_bytes(settings, date, filename))
