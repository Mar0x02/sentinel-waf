from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalog import CRS_CATALOG, CatalogEntry, get_catalog_entry
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Rule, RuleFile, RuleSet
from app.schemas.rule_sets import (
    CustomRuleFileCreate,
    CustomRuleFileUpdate,
    EnabledPatch,
    ImportFromCatalogRequest,
    ImportFromUrlRequest,
    RuleFileContentOut,
    RuleFileOut,
    RuleOut,
    RuleSetOut,
)
from app.services import importer, render_service
from app.services.importer import CUSTOM_RULE_SET_SLUG

router = APIRouter(prefix="/api", tags=["rules"])


def _rule_set_out(db: Session, rule_set: RuleSet) -> RuleSetOut:
    file_count = db.query(func.count(RuleFile.id)).filter(RuleFile.rule_set_id == rule_set.id).scalar()
    rule_count = (
        db.query(func.count(Rule.id))
        .join(RuleFile, Rule.rule_file_id == RuleFile.id)
        .filter(RuleFile.rule_set_id == rule_set.id)
        .scalar()
    )
    return RuleSetOut(
        id=rule_set.id,
        name=rule_set.name,
        slug=rule_set.slug,
        source_type=rule_set.source_type,
        source_url=rule_set.source_url,
        version=rule_set.version,
        order_seq=rule_set.order_seq,
        enabled=rule_set.enabled,
        created_at=rule_set.created_at,
        file_count=file_count or 0,
        rule_count=rule_count or 0,
    )


def _rule_file_out(db: Session, rule_file: RuleFile) -> RuleFileOut:
    rule_count = db.query(func.count(Rule.id)).filter(Rule.rule_file_id == rule_file.id).scalar()
    return RuleFileOut(
        id=rule_file.id,
        rule_set_id=rule_file.rule_set_id,
        filename=rule_file.filename,
        file_kind=rule_file.file_kind,
        enabled=rule_file.enabled,
        size_bytes=len(rule_file.content.encode()),
        rule_count=rule_count or 0,
        created_at=rule_file.created_at,
        updated_at=rule_file.updated_at,
    )


def _rerender(db: Session, settings: Settings) -> None:
    render_service.render_rules(db, settings)


@router.get("/catalog", response_model=list[CatalogEntry])
def list_catalog():
    return CRS_CATALOG


@router.get("/rule-sets", response_model=list[RuleSetOut])
def list_rule_sets(db: Session = Depends(get_db)):
    rule_sets = db.query(RuleSet).order_by(RuleSet.order_seq).all()
    return [_rule_set_out(db, rs) for rs in rule_sets]


@router.post("/rule-sets/import-catalog", response_model=RuleSetOut, status_code=201)
def import_catalog(
    payload: ImportFromCatalogRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    entry = get_catalog_entry(payload.catalog_id)
    if entry is None:
        raise HTTPException(404, f"Unknown catalog entry '{payload.catalog_id}'")
    try:
        rule_set = importer.import_from_url(db, name=entry.name, url=entry.url, version=entry.version)
    except importer.ImportError_ as e:
        raise HTTPException(400, str(e))
    _rerender(db, settings)
    return _rule_set_out(db, rule_set)


@router.post("/rule-sets/import-url", response_model=RuleSetOut, status_code=201)
def import_url(
    payload: ImportFromUrlRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        rule_set = importer.import_from_url(db, name=payload.name, url=payload.url, version=payload.version)
    except importer.ImportError_ as e:
        raise HTTPException(400, str(e))
    _rerender(db, settings)
    return _rule_set_out(db, rule_set)


@router.patch("/rule-sets/{rule_set_id}", response_model=RuleSetOut)
def toggle_rule_set(
    rule_set_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    rule_set.enabled = payload.enabled
    db.commit()
    _rerender(db, settings)
    return _rule_set_out(db, rule_set)


@router.delete("/rule-sets/{rule_set_id}", status_code=204)
def delete_rule_set(
    rule_set_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    if rule_set.slug == CUSTOM_RULE_SET_SLUG:
        raise HTTPException(400, "The custom rule set can't be deleted")
    db.delete(rule_set)
    db.commit()
    _rerender(db, settings)


@router.get("/rule-sets/{rule_set_id}/files", response_model=list[RuleFileOut])
def list_rule_files(rule_set_id: int, db: Session = Depends(get_db)):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    return [_rule_file_out(db, rf) for rf in rule_set.files]


@router.post("/rule-files", response_model=RuleFileOut, status_code=201)
def create_rule_file(
    payload: CustomRuleFileCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        rule_file = importer.create_custom_rule_file(db, filename=payload.filename, content=payload.content)
    except importer.ImportError_ as e:
        raise HTTPException(409, str(e))
    _rerender(db, settings)
    return _rule_file_out(db, rule_file)


@router.get("/rule-files/{rule_file_id}", response_model=RuleFileContentOut)
def read_rule_file(rule_file_id: int, db: Session = Depends(get_db)):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    return RuleFileContentOut(id=rule_file.id, filename=rule_file.filename, content=rule_file.content)


@router.put("/rule-files/{rule_file_id}", response_model=RuleFileOut)
def update_rule_file(
    rule_file_id: int,
    payload: CustomRuleFileUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    if rule_file.rule_set.slug != CUSTOM_RULE_SET_SLUG:
        raise HTTPException(
            403,
            "Only custom rule files can be edited directly - disable individual rules or "
            "the whole file/rule set instead of editing imported content.",
        )
    rule_file = importer.update_custom_rule_file(db, rule_file, payload.content)
    _rerender(db, settings)
    return _rule_file_out(db, rule_file)


@router.patch("/rule-files/{rule_file_id}", response_model=RuleFileOut)
def toggle_rule_file(
    rule_file_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    rule_file.enabled = payload.enabled
    db.commit()
    _rerender(db, settings)
    return _rule_file_out(db, rule_file)


@router.delete("/rule-files/{rule_file_id}", status_code=204)
def delete_rule_file(
    rule_file_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    if rule_file.rule_set.slug != CUSTOM_RULE_SET_SLUG:
        raise HTTPException(403, "Only custom rule files can be deleted directly - delete the whole rule set instead.")
    db.delete(rule_file)
    db.commit()
    _rerender(db, settings)


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    rule_file_id: int | None = None,
    rule_set_id: int | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Rule)
    if rule_file_id is not None:
        query = query.filter(Rule.rule_file_id == rule_file_id)
    if rule_set_id is not None:
        query = query.join(RuleFile, Rule.rule_file_id == RuleFile.id).filter(RuleFile.rule_set_id == rule_set_id)
    if search:
        like = f"%{search}%"
        query = query.filter((Rule.rule_id.ilike(like)) | (Rule.message.ilike(like)))
    return query.order_by(Rule.rule_file_id, Rule.order_index).offset(offset).limit(limit).all()


@router.patch("/rules/{rule_id}", response_model=RuleOut)
def toggle_rule(
    rule_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    rule.enabled = payload.enabled
    db.commit()
    _rerender(db, settings)
    return rule
