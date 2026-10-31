from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.default_error_pages import DEFAULT_ERROR_PAGES, ERROR_PAGE_TITLES
from app.models import ErrorPage
from app.schemas.error_pages import ErrorPageOut, ErrorPageUpdate
from app.services import render_service

router = APIRouter(prefix="/api/error-pages", tags=["error-pages"])


def _to_out(status_code: int, row: ErrorPage | None) -> ErrorPageOut:
    return ErrorPageOut(
        status_code=status_code,
        title=ERROR_PAGE_TITLES[status_code],
        html_content=row.html_content if row else DEFAULT_ERROR_PAGES[status_code],
        is_customized=row is not None,
        updated_at=row.updated_at if row else None,
    )


@router.get("", response_model=list[ErrorPageOut])
def list_error_pages(db: Session = Depends(get_db)):
    rows = {row.status_code: row for row in db.query(ErrorPage).all()}
    return [_to_out(code, rows.get(code)) for code in sorted(DEFAULT_ERROR_PAGES)]


@router.get("/{status_code}", response_model=ErrorPageOut)
def get_error_page(status_code: int, db: Session = Depends(get_db)):
    if status_code not in DEFAULT_ERROR_PAGES:
        raise HTTPException(404, f"Status code {status_code} isn't supported")
    row = db.get(ErrorPage, status_code)
    return _to_out(status_code, row)


@router.put("/{status_code}", response_model=ErrorPageOut)
def update_error_page(
    status_code: int,
    payload: ErrorPageUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if status_code not in DEFAULT_ERROR_PAGES:
        raise HTTPException(404, f"Status code {status_code} isn't supported")
    row = db.get(ErrorPage, status_code)
    if row is None:
        row = ErrorPage(status_code=status_code, html_content=payload.html_content)
        db.add(row)
    else:
        row.html_content = payload.html_content
    db.commit()
    render_service.render_error_pages(db, settings)
    return _to_out(status_code, row)


@router.post("/{status_code}/reset", response_model=ErrorPageOut)
def reset_error_page(
    status_code: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if status_code not in DEFAULT_ERROR_PAGES:
        raise HTTPException(404, f"Status code {status_code} isn't supported")
    row = db.get(ErrorPage, status_code)
    if row is not None:
        db.delete(row)
        db.commit()
    render_service.render_error_pages(db, settings)
    return _to_out(status_code, None)
