from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.auth import require_write_access
from app.config import Settings, get_settings
from app.schemas.logs import ArchiveDate, ArchiveFile
from app.services import log_archive_service

# Separate router/prefix from logs.py's /api/logs on purpose - that router
# already has a GET /api/logs/{transaction_id} catch-all path param, which
# would greedily swallow a literal "/api/logs/archive/..." segment if this
# were nested under it instead (Starlette matches routes in registration
# order, not by specificity).
router = APIRouter(prefix="/api/log-archive", tags=["logs"])


@router.get("/dates", response_model=list[ArchiveDate])
def list_dates(settings: Settings = Depends(get_settings)):
    return log_archive_service.list_dates(settings)


@router.get("/dates/{date}", response_model=list[ArchiveFile])
def list_files(date: str, settings: Settings = Depends(get_settings)):
    try:
        return log_archive_service.list_files(settings, date)
    except ValueError:
        raise HTTPException(400, "Invalid date")


@router.get("/dates/{date}/{filename}/download")
def download_file(
    date: str,
    filename: str,
    format: str = Query("gz", pattern="^(gz|log)$"),
    settings: Settings = Depends(get_settings),
):
    try:
        if format == "gz":
            content = log_archive_service.read_gz_bytes(settings, date, filename)
            media_type = "application/gzip"
            download_name = filename
        else:
            content = log_archive_service.read_decompressed(settings, date, filename)
            media_type = "application/jsonl"
            download_name = filename.removesuffix(".gz") + ".log"
    except ValueError:
        raise HTTPException(400, "Invalid date or filename")
    except FileNotFoundError:
        raise HTTPException(404, "Archived log file not found")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.delete("/dates/{date}/{filename}", status_code=204, dependencies=[Depends(require_write_access)])
def delete_file(date: str, filename: str, settings: Settings = Depends(get_settings)):
    try:
        deleted = log_archive_service.delete_file(settings, date, filename)
    except ValueError:
        raise HTTPException(400, "Invalid date or filename")
    if not deleted:
        raise HTTPException(404, "Archived log file not found")
