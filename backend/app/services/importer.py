import io
import re
import tarfile
import zipfile
from pathlib import PurePosixPath

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FileKind, Rule, RuleFile, RuleSet, SourceType
from app.services.rule_parser import parse_rules

CUSTOM_RULE_SET_SLUG = "custom"


class ImportError_(Exception):
    pass


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "rule-set"


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    i = 2
    while db.query(RuleSet).filter(RuleSet.slug == slug).first() is not None:
        slug = f"{base}-{i}"
        i += 1
    return slug


def _next_order_seq(db: Session) -> int:
    return (db.query(func.max(RuleSet.order_seq)).scalar() or 0) + 1


def _classify(basename: str) -> FileKind | None:
    if basename == "crs-setup.conf.example" or basename == "crs-setup.conf":
        return FileKind.setup
    if basename.endswith(".conf"):
        return FileKind.setup if "setup" in basename.lower() else FileKind.rule
    if basename.endswith(".data"):
        return FileKind.asset
    return None


def _normalize_filename(basename: str) -> str:
    if basename == "crs-setup.conf.example":
        return "crs-setup.conf"
    return basename


def _extract_members(raw: bytes) -> list[tuple[str, bytes]]:
    """Returns (basename, content) for every rule-relevant file found.

    Not CRS-specific: any .conf/.data file anywhere in the archive is
    picked up by basename, so an arbitrary custom rule package works too.
    Collisions between same-basename files in different subdirectories are
    resolved by last-wins - acceptable for the curated CRS catalog, a
    documented limitation for arbitrary uploaded archives (see CLAUDE.md).
    """
    members: dict[str, bytes] = {}

    if raw[:2] == b"\x1f\x8b":  # gzip magic -> tar.gz
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                basename = PurePosixPath(member.name).name
                if _classify(basename) is None:
                    continue
                extracted = tar.extractfile(member)
                if extracted is not None:
                    members[_normalize_filename(basename)] = extracted.read()
    elif raw[:4] == b"PK\x03\x04":  # zip magic
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                basename = PurePosixPath(info.filename).name
                if _classify(basename) is None:
                    continue
                members[_normalize_filename(basename)] = z.read(info)
    else:
        # Not an archive - treat the whole response as a single rule file.
        members["imported-rule.conf"] = raw

    return list(members.items())


def import_from_url(db: Session, *, name: str, url: str, version: str | None = None) -> RuleSet:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise ImportError_(f"Failed to download '{url}': {e}") from e

    members = _extract_members(resp.content)
    if not members:
        raise ImportError_("No .conf/.data rule files found at that URL")

    slug = _unique_slug(db, _slugify(f"{name}-{version}" if version else name))
    rule_set = RuleSet(
        name=name,
        slug=slug,
        source_type=SourceType.url,
        source_url=url,
        version=version,
        order_seq=_next_order_seq(db),
    )
    db.add(rule_set)
    db.flush()

    for basename, content_bytes in members:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue
        kind = _classify(basename) or FileKind.rule
        rule_file = RuleFile(rule_set_id=rule_set.id, filename=basename, content=text, file_kind=kind)
        db.add(rule_file)
        db.flush()
        if kind != FileKind.asset:
            for parsed in parse_rules(text):
                db.add(
                    Rule(
                        rule_file_id=rule_file.id,
                        rule_id=parsed.rule_id,
                        message=parsed.message,
                        raw_snippet=parsed.raw_snippet,
                        order_index=parsed.order_index,
                    )
                )

    db.commit()
    db.refresh(rule_set)
    return rule_set


def ensure_custom_rule_set(db: Session) -> RuleSet:
    existing = db.query(RuleSet).filter(RuleSet.slug == CUSTOM_RULE_SET_SLUG).first()
    if existing:
        return existing
    rule_set = RuleSet(
        name="Custom Rules",
        slug=CUSTOM_RULE_SET_SLUG,
        source_type=SourceType.custom,
        order_seq=_next_order_seq(db),
    )
    db.add(rule_set)
    db.commit()
    db.refresh(rule_set)
    return rule_set


def create_custom_rule_file(db: Session, *, filename: str, content: str) -> RuleFile:
    rule_set = ensure_custom_rule_set(db)
    existing = (
        db.query(RuleFile)
        .filter(RuleFile.rule_set_id == rule_set.id, RuleFile.filename == filename)
        .first()
    )
    if existing:
        raise ImportError_(f"Rule file '{filename}' already exists")

    rule_file = RuleFile(rule_set_id=rule_set.id, filename=filename, content=content, file_kind=FileKind.rule)
    db.add(rule_file)
    db.flush()
    _reparse_rules(db, rule_file)
    db.commit()
    db.refresh(rule_file)
    return rule_file


def update_custom_rule_file(db: Session, rule_file: RuleFile, content: str) -> RuleFile:
    rule_file.content = content
    db.flush()
    _reparse_rules(db, rule_file)
    db.commit()
    db.refresh(rule_file)
    return rule_file


def _reparse_rules(db: Session, rule_file: RuleFile) -> None:
    db.query(Rule).filter(Rule.rule_file_id == rule_file.id).delete()
    for parsed in parse_rules(rule_file.content):
        db.add(
            Rule(
                rule_file_id=rule_file.id,
                rule_id=parsed.rule_id,
                message=parsed.message,
                raw_snippet=parsed.raw_snippet,
                order_index=parsed.order_index,
            )
        )
