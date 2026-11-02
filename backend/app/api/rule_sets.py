from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_write_access
from app.catalog import CRS_CATALOG, CatalogEntry, get_catalog_entry
from app.config import Settings, get_settings
from app.db import get_db
from app.models import FileKind, Rule, RuleFile, RuleFileVersion, RuleSet
from app.schemas.rule_sets import (
    CrsTuningOut,
    CrsTuningUpdate,
    CustomRuleFileCreate,
    CustomRuleFileUpdate,
    EnabledPatch,
    ImportFromCatalogRequest,
    ImportFromUrlRequest,
    InitCollectionRequest,
    LintRequest,
    LintResult,
    RuleFileContentOut,
    RuleFileOut,
    RuleFileVersionOut,
    RuleOut,
    RuleSetOut,
    SetupFileStatusOut,
    TunableFixOut,
    TunableGroupCreate,
    TunableGroupOut,
    TunableGroupUpdate,
    TxVarWarningOut,
)
from app.services import crs_tuning, importer, render_service, tunable_scanner, tx_var_linter
from app.services.importer import CUSTOM_RULE_SET_SLUG

# Rule IDs already covered by the dedicated paranoia/anomaly form
# (crs_tuning.py) plus CRS's own version marker (900990, not a real
# tunable) - excluded from the generic scanner's results so the Rules
# page doesn't show the same knob twice under two different UIs.
_EXCLUDED_TUNABLE_IDS = {"900000", "900001", "900110", "900990"}

router = APIRouter(prefix="/api", tags=["rules"])


def _rule_set_out(db: Session, rule_set: RuleSet, carried_over_tunables: list[str] | None = None) -> RuleSetOut:
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
        carried_over_tunables=carried_over_tunables or [],
    )


def _rule_file_out(db: Session, rule_file: RuleFile, warnings: list[TxVarWarningOut] | None = None) -> RuleFileOut:
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
        warnings=warnings or [],
    )


def _lint(db: Session, content: str, exclude_rule_file_id: int | None = None) -> list[TxVarWarningOut]:
    checks = (
        tx_var_linter.lint_tx_vars(db, content, exclude_rule_file_id=exclude_rule_file_id)
        + tx_var_linter.lint_collection_init(db, content, exclude_rule_file_id=exclude_rule_file_id)
        + tx_var_linter.lint_unused_counters(db, content, exclude_rule_file_id=exclude_rule_file_id)
    )
    return [
        TxVarWarningOut(
            variable=w.variable,
            rule_id=w.rule_id,
            snippet=w.snippet,
            kind=w.kind,
            fix=TunableFixOut(
                rule_set_id=w.fix.rule_set_id,
                rule_set_name=w.fix.rule_set_name,
                tunable_rule_id=w.fix.tunable_rule_id,
                variables=w.fix.variables,
                is_new=w.fix.is_new,
                init_collection=w.fix.init_collection,
            )
            if w.fix
            else None,
        )
        for w in checks
    ]


def _rerender(db: Session, settings: Settings) -> None:
    render_service.render_rules(db, settings)


@router.get("/catalog", response_model=list[CatalogEntry])
def list_catalog():
    return CRS_CATALOG


@router.get("/rule-sets", response_model=list[RuleSetOut])
def list_rule_sets(db: Session = Depends(get_db)):
    rule_sets = db.query(RuleSet).order_by(RuleSet.order_seq).all()
    return [_rule_set_out(db, rs) for rs in rule_sets]


@router.get("/rule-sets/{rule_set_id}", response_model=RuleSetOut)
def get_rule_set(rule_set_id: int, db: Session = Depends(get_db)):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    return _rule_set_out(db, rule_set)


@router.get("/rule-sets/{rule_set_id}/other-setup-files", response_model=list[SetupFileStatusOut])
def list_other_setup_files(rule_set_id: int, db: Session = Depends(get_db)):
    """Every *other* rule set's setup file (crs-setup.conf-equivalent),
    for Base Tuning's detail page to show as a read-only status overview -
    see CLAUDE.md on why Base Tuning never copies/edits these files
    directly, only reads their current enabled state.
    """
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    setup_files = (
        db.query(RuleFile)
        .join(RuleSet, RuleFile.rule_set_id == RuleSet.id)
        .filter(RuleFile.file_kind == FileKind.setup, RuleSet.id != rule_set_id)
        .order_by(RuleSet.order_seq)
        .all()
    )
    return [
        SetupFileStatusOut(
            rule_set_id=rf.rule_set.id,
            rule_set_name=rf.rule_set.name,
            rule_set_slug=rf.rule_set.slug,
            rule_file_id=rf.id,
            filename=rf.filename,
            size_bytes=len(rf.content.encode()),
            in_use=rf.rule_set.enabled and rf.enabled,
        )
        for rf in setup_files
    ]


@router.post("/rule-sets/import-catalog", response_model=RuleSetOut, status_code=201)
def import_catalog(
    payload: ImportFromCatalogRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    entry = get_catalog_entry(payload.catalog_id)
    if entry is None:
        raise HTTPException(404, f"Unknown catalog entry '{payload.catalog_id}'")
    try:
        rule_set, carried_over = importer.import_from_url(db, name=entry.name, url=entry.url, version=entry.version)
    except importer.ImportError_ as e:
        raise HTTPException(400, str(e))
    _rerender(db, settings)
    return _rule_set_out(db, rule_set, carried_over)


@router.post("/rule-sets/import-url", response_model=RuleSetOut, status_code=201)
def import_url(
    payload: ImportFromUrlRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    try:
        rule_set, carried_over = importer.import_from_url(db, name=payload.name, url=payload.url, version=payload.version)
    except importer.ImportError_ as e:
        raise HTTPException(400, str(e))
    _rerender(db, settings)
    return _rule_set_out(db, rule_set, carried_over)


@router.patch("/rule-sets/{rule_set_id}", response_model=RuleSetOut)
def toggle_rule_set(
    rule_set_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
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
    _=Depends(require_write_access),
):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    if rule_set.slug in (CUSTOM_RULE_SET_SLUG, importer.BASE_TUNING_RULE_SET_SLUG):
        raise HTTPException(400, "This rule set can't be deleted")
    db.delete(rule_set)
    db.commit()
    _rerender(db, settings)


@router.post("/rule-sets/{rule_set_id}/sync-from-base-tuning", response_model=list[str])
def sync_from_base_tuning(
    rule_set_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    """Copies Base Tuning's active tunable values onto this (typically an
    imported CRS) rule set's own setup file, wherever the id and variable
    names match exactly - same matching rule as the import-time carry-over
    (tunable_scanner.carry_over_tunables), just triggered on demand here
    instead of automatically at import time, and in the reverse direction
    (Base Tuning -> this rule set, rather than old rule set -> newly
    imported one). Goes through update_custom_rule_file so this creates a
    new version snapshot - the pristine imported content stays one revert
    away, never overwritten destructively.
    """
    base_tuning = db.query(RuleSet).filter(RuleSet.slug == importer.BASE_TUNING_RULE_SET_SLUG).first()
    if base_tuning is None or rule_set_id == base_tuning.id:
        raise HTTPException(400, "Base Tuning can't sync from itself")
    target_setup = _get_setup_file(db, rule_set_id)
    base_tuning_setup = _get_setup_file(db, base_tuning.id)
    merged_content, applied = tunable_scanner.sync_from_source(base_tuning_setup.content, target_setup.content)
    if applied:
        importer.update_custom_rule_file(db, target_setup, merged_content)
        _rerender(db, settings)
    return applied


@router.get("/rule-sets/{rule_set_id}/files", response_model=list[RuleFileOut])
def list_rule_files(rule_set_id: int, db: Session = Depends(get_db)):
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    # Lint every file here too, not just the raw-edit save path - this is
    # what feeds the Rules page's "View rules" modal, which previously
    # always showed warnings: [] regardless of whether a rule actually
    # referenced an undefined tx.* var (caught via a real custom rule that
    # referenced a still-commented-out CRS tunable).
    return [_rule_file_out(db, rf, warnings=_lint(db, rf.content, exclude_rule_file_id=rf.id)) for rf in rule_set.files]


def _get_setup_file(db: Session, rule_set_id: int) -> RuleFile:
    rule_set = db.get(RuleSet, rule_set_id)
    if rule_set is None:
        raise HTTPException(404, "Rule set not found")
    setup_file = next((rf for rf in rule_set.files if rf.file_kind == FileKind.setup), None)
    if setup_file is None:
        raise HTTPException(404, "This rule set has no setup file (e.g. crs-setup.conf) to tune")
    return setup_file


@router.get("/rule-sets/{rule_set_id}/tuning", response_model=CrsTuningOut)
def get_tuning(rule_set_id: int, db: Session = Depends(get_db)):
    setup_file = _get_setup_file(db, rule_set_id)
    return crs_tuning.read_tuning(setup_file.content)


@router.put("/rule-sets/{rule_set_id}/tuning", response_model=CrsTuningOut)
def update_tuning(
    rule_set_id: int,
    payload: CrsTuningUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    setup_file = _get_setup_file(db, rule_set_id)
    new_content = crs_tuning.write_tuning(
        setup_file.content,
        crs_tuning.CrsTuning(
            blocking_paranoia_level=payload.blocking_paranoia_level,
            detection_paranoia_level=payload.detection_paranoia_level,
            inbound_anomaly_score_threshold=payload.inbound_anomaly_score_threshold,
            outbound_anomaly_score_threshold=payload.outbound_anomaly_score_threshold,
        ),
    )
    importer.update_custom_rule_file(db, setup_file, new_content)
    _rerender(db, settings)
    return crs_tuning.read_tuning(new_content)


@router.get("/rule-sets/{rule_set_id}/tunables", response_model=list[TunableGroupOut])
def list_tunables(rule_set_id: int, db: Session = Depends(get_db)):
    setup_file = _get_setup_file(db, rule_set_id)
    groups = tunable_scanner.scan_tunables(setup_file.content, exclude_rule_ids=_EXCLUDED_TUNABLE_IDS)
    return [TunableGroupOut(**vars(g)) for g in groups]


@router.put("/rule-sets/{rule_set_id}/tunables/{tunable_rule_id}", response_model=TunableGroupOut)
def update_tunable(
    rule_set_id: int,
    tunable_rule_id: str,
    payload: TunableGroupUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    if tunable_rule_id in _EXCLUDED_TUNABLE_IDS:
        raise HTTPException(400, "Use the dedicated tuning endpoint for this one")
    setup_file = _get_setup_file(db, rule_set_id)
    try:
        new_content = tunable_scanner.apply_tunable(
            setup_file.content, tunable_rule_id, payload.variables, payload.is_active
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    importer.update_custom_rule_file(db, setup_file, new_content)
    _rerender(db, settings)
    groups = tunable_scanner.scan_tunables(new_content, exclude_rule_ids=set())
    updated = next(g for g in groups if g.rule_id == tunable_rule_id)
    return TunableGroupOut(**vars(updated))


@router.post("/rule-sets/{rule_set_id}/tunables", response_model=TunableGroupOut, status_code=201)
def create_tunable(
    rule_set_id: int,
    payload: TunableGroupCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    """Appends a brand-new tunable block - used by the lint warning's
    "add it" fix (see tx_var_linter.py) when no existing tunable anywhere
    already defines the referenced var, so there's nothing for the PUT
    endpoint above to activate."""
    setup_file = _get_setup_file(db, rule_set_id)
    existing_ids = {g.rule_id for g in tunable_scanner.scan_tunables(setup_file.content)}
    if payload.rule_id in existing_ids:
        raise HTTPException(409, f"id:{payload.rule_id} already exists in this setup file")
    new_content = tunable_scanner.add_tunable(setup_file.content, payload.rule_id, payload.variables, payload.phase)
    importer.update_custom_rule_file(db, setup_file, new_content)
    _rerender(db, settings)
    groups = tunable_scanner.scan_tunables(new_content, exclude_rule_ids=set())
    created = next(g for g in groups if g.rule_id == payload.rule_id)
    return TunableGroupOut(**vars(created))


@router.post("/rule-sets/{rule_set_id}/init-collection", response_model=TunableGroupOut, status_code=201)
def init_collection(
    rule_set_id: int,
    payload: InitCollectionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    """Appends initcol:<collection>=%{REMOTE_ADDR} - used by the lint
    warning's fix for "uninitialized_collection" (see tx_var_linter.py).
    Not a setvar:tx.X=Y tunable, so this doesn't go through create_tunable
    above - add_raw_action() builds the block instead. Doesn't re-derive
    the response via scan_tunables() like create_tunable does, because
    scan_tunables only recognizes blocks containing a setvar:tx.* (see its
    _SETVAR_RE) - an initcol-only block would never match and this would
    404 on its own output.
    """
    setup_file = _get_setup_file(db, rule_set_id)
    existing_ids = {g.rule_id for g in tunable_scanner.scan_tunables(setup_file.content)}
    if payload.rule_id in existing_ids:
        raise HTTPException(409, f"id:{payload.rule_id} already exists in this setup file")
    new_content = tunable_scanner.add_raw_action(
        setup_file.content, payload.rule_id, payload.phase, [f"initcol:{payload.collection}=%{{REMOTE_ADDR}}"]
    )
    importer.update_custom_rule_file(db, setup_file, new_content)
    _rerender(db, settings)
    return TunableGroupOut(
        rule_id=payload.rule_id,
        description=f"initcol:{payload.collection}",
        is_active=True,
        variables={},
    )


@router.post("/rule-files", response_model=RuleFileOut, status_code=201)
def create_rule_file(
    payload: CustomRuleFileCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    try:
        rule_file = importer.create_custom_rule_file(db, filename=payload.filename, content=payload.content)
    except importer.ImportError_ as e:
        raise HTTPException(409, str(e))
    _rerender(db, settings)
    warnings = _lint(db, rule_file.content, exclude_rule_file_id=rule_file.id)
    return _rule_file_out(db, rule_file, warnings)


@router.post("/rule-files/lint", response_model=LintResult)
def lint_rule_file(payload: LintRequest, db: Session = Depends(get_db)):
    """Advisory-only check, never blocks a save - see
    app.services.tx_var_linter's module docstring. Lets the editor warn
    about an undefined tx.* reference before the user even hits Save,
    not just after."""
    return LintResult(warnings=_lint(db, payload.content, exclude_rule_file_id=payload.rule_file_id))


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
    _=Depends(require_write_access),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    # "setup" files (crs-setup.conf and friends) are meant to be tuned per
    # deployment - that's their whole purpose, unlike the rule files
    # proper, which stay locked so an imported set remains trustworthy
    # relative to its source. See CLAUDE.md.
    if rule_file.rule_set.slug != CUSTOM_RULE_SET_SLUG and rule_file.file_kind != FileKind.setup:
        raise HTTPException(
            403,
            "Only custom rule files and setup files (e.g. crs-setup.conf) can be edited directly - "
            "disable individual rules or the whole file/rule set instead of editing imported rule content.",
        )
    rule_file = importer.update_custom_rule_file(db, rule_file, payload.content)
    _rerender(db, settings)
    warnings = _lint(db, rule_file.content, exclude_rule_file_id=rule_file.id)
    return _rule_file_out(db, rule_file, warnings)


@router.patch("/rule-files/{rule_file_id}", response_model=RuleFileOut)
def toggle_rule_file(
    rule_file_id: int,
    payload: EnabledPatch,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
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
    _=Depends(require_write_access),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    if rule_file.rule_set.slug != CUSTOM_RULE_SET_SLUG:
        raise HTTPException(403, "Only custom rule files can be deleted directly - delete the whole rule set instead.")
    db.delete(rule_file)
    db.commit()
    _rerender(db, settings)


@router.get("/rule-files/{rule_file_id}/versions", response_model=list[RuleFileVersionOut])
def list_rule_file_versions(rule_file_id: int, db: Session = Depends(get_db)):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    versions = (
        db.query(RuleFileVersion)
        .filter(RuleFileVersion.rule_file_id == rule_file_id)
        .order_by(RuleFileVersion.created_at.desc())
        .all()
    )
    return [
        RuleFileVersionOut(id=v.id, created_at=v.created_at, content=v.content, size_bytes=len(v.content.encode()))
        for v in versions
    ]


@router.post("/rule-files/{rule_file_id}/versions/{version_id}/revert", response_model=RuleFileOut)
def revert_rule_file(
    rule_file_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _=Depends(require_write_access),
):
    rule_file = db.get(RuleFile, rule_file_id)
    if rule_file is None:
        raise HTTPException(404, "Rule file not found")
    version = db.get(RuleFileVersion, version_id)
    if version is None or version.rule_file_id != rule_file_id:
        raise HTTPException(404, "Version not found")
    # Goes through the same snapshot-on-write hook as every other save, so
    # the content being replaced here is itself saved as a new version
    # first - a revert is always itself undoable.
    rule_file = importer.update_custom_rule_file(db, rule_file, version.content)
    _rerender(db, settings)
    warnings = _lint(db, rule_file.content, exclude_rule_file_id=rule_file.id)
    return _rule_file_out(db, rule_file, warnings)


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
    _=Depends(require_write_access),
):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    rule.enabled = payload.enabled
    db.commit()
    _rerender(db, settings)
    return rule
