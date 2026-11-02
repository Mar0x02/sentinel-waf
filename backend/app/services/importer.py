import io
import ipaddress
import re
import socket
import tarfile
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.default_base_tuning import DEFAULT_BASE_TUNING_CONFIG
from app.models import FileKind, Rule, RuleFile, RuleFileVersion, RuleSet, SourceType
from app.services import tunable_scanner
from app.services.rule_parser import parse_rules

CUSTOM_RULE_SET_SLUG = "custom"
# Standalone, CRS-independent anomaly-scoring scaffold - see
# app/default_base_tuning.py. Seeded once at startup like the custom rule
# set, never deletable (see api/rule_sets.py's delete_rule_set), and
# rendered into zzz-overrides/ rather than its own directory slot - see
# render_service.render_rules().
BASE_TUNING_RULE_SET_SLUG = "base-tuning"


class ImportError_(Exception):
    pass


# RFC 6052 NAT64 "Well-Known Prefix" - Docker Desktop's resolver can
# synthesize one of these for a plain IPv4-only hostname (observed for
# github.com in testing: alongside the real A record, getaddrinfo also
# returned 64:ff9b::14cd:f3a6, which embeds 20.205.243.166 - the exact
# same address - in its low 32 bits). It's a legitimate translation
# mechanism, not attacker-controlled, so the embedded IPv4 is checked
# instead of rejecting the synthesized wrapper outright.
_NAT64_WKP = ipaddress.ip_network("64:ff9b::/96")


def _effective_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    if isinstance(ip, ipaddress.IPv6Address) and ip in _NAT64_WKP:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    ip = _effective_ip(ip)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def _reject_private_target(url: str) -> None:
    """SSRF guard for "import rule set from URL": this endpoint makes the
    *backend* fetch an admin/operator-supplied URL server-side, which
    would otherwise let that role reach internal-only services - e.g.
    http://postgres:5432, http://backend:8000, or (same bug class as any
    cloud box) http://169.254.169.254/ for instance metadata. Docker
    Compose service names resolve to addresses in the compose network's
    private range, so resolving the hostname and rejecting any private/
    loopback/link-local/reserved result catches both "obviously internal
    hostname" and "DNS rebinding to an internal IP" in one check.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImportError_("url must be a valid http:// or https:// URL")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise ImportError_(f"Could not resolve host '{parsed.hostname}': {e}") from e

    for *_rest, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise ImportError_(
                f"'{parsed.hostname}' resolves to a private/internal address ({ip}) - "
                "only public URLs can be imported"
            )


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


def _fetch_public_url(url: str, *, max_redirects: int = 5) -> bytes:
    """GETs `url`, validating every hop (not just the first) against
    _reject_private_target - a redirect is exactly how an SSRF guard that
    only checks the original URL gets bypassed (pass a public URL that
    302s to an internal one). CRS's own GitHub release assets genuinely
    redirect through objects.githubusercontent.com, so redirects can't
    just be disabled - they have to be followed one at a time and
    re-validated.
    """
    current = url
    for _ in range(max_redirects + 1):
        _reject_private_target(current)
        try:
            resp = httpx.get(current, follow_redirects=False, timeout=30.0)
        except httpx.HTTPError as e:
            raise ImportError_(f"Failed to download '{current}': {e}") from e
        if resp.is_redirect:
            location = resp.headers.get("location")
            if not location:
                raise ImportError_(f"'{current}' redirected without a Location header")
            current = str(httpx.URL(current).join(location))
            continue
        resp.raise_for_status()
        return resp.content
    raise ImportError_("Too many redirects")


def _carry_over_crs_tuning(db: Session, new_rule_set: RuleSet) -> list[str]:
    """After importing a new rule set, if it has a setup file (e.g.
    crs-setup.conf) and some OTHER existing rule set also has one with
    active tunables, copy forward whatever matches exactly - see
    tunable_scanner.carry_over_tunables. Picks the most recently created
    other rule set with a setup file as the source; if that happens to be
    a different CRS major version (or an unrelated vendor), mismatched
    tunables are simply skipped there, never misapplied.

    Reuses update_custom_rule_file() for the actual write so this gets the
    same version-snapshot-before-overwrite behavior as any other setup
    file edit (see models.RuleFileVersion) - the as-imported pristine
    content is never lost, just one History-panel revert away.
    """
    new_setup = next((f for f in new_rule_set.files if f.file_kind == FileKind.setup), None)
    if new_setup is None:
        return []

    source_file = (
        db.query(RuleFile)
        .join(RuleSet, RuleFile.rule_set_id == RuleSet.id)
        .filter(RuleFile.file_kind == FileKind.setup, RuleSet.id != new_rule_set.id)
        .order_by(RuleSet.created_at.desc())
        .first()
    )
    if source_file is None:
        return []

    merged_content, applied = tunable_scanner.carry_over_tunables(source_file.content, new_setup.content)
    if applied:
        update_custom_rule_file(db, new_setup, merged_content)
    return applied


def import_from_url(db: Session, *, name: str, url: str, version: str | None = None) -> tuple[RuleSet, list[str]]:
    try:
        content = _fetch_public_url(url)
    except httpx.HTTPError as e:
        raise ImportError_(f"Failed to download '{url}': {e}") from e

    members = _extract_members(content)
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
    carried_over = _carry_over_crs_tuning(db, rule_set)
    return rule_set, carried_over


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


def ensure_base_tuning_rule_set(db: Session) -> RuleSet:
    existing = db.query(RuleSet).filter(RuleSet.slug == BASE_TUNING_RULE_SET_SLUG).first()
    if existing:
        return existing
    rule_set = RuleSet(
        name="Base Tuning",
        slug=BASE_TUNING_RULE_SET_SLUG,
        source_type=SourceType.custom,
        order_seq=_next_order_seq(db),
    )
    db.add(rule_set)
    db.flush()
    rule_file = RuleFile(
        rule_set_id=rule_set.id,
        filename="base-tuning.conf",
        content=DEFAULT_BASE_TUNING_CONFIG,
        file_kind=FileKind.setup,
    )
    db.add(rule_file)
    db.flush()
    for parsed in parse_rules(DEFAULT_BASE_TUNING_CONFIG):
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
    # Snapshot the pre-change content for setup files (e.g. crs-setup.conf)
    # so it can be reverted later - see models.RuleFileVersion. This is the
    # one function CRS Tuning, the generic Tunables panel, and raw edit all
    # funnel through, so it's the single place this needs to live. Plain
    # rule files are never snapshotted (not the scope of the revert
    # feature, and they're mostly read-only anyway).
    if rule_file.file_kind == FileKind.setup and content != rule_file.content:
        db.add(RuleFileVersion(rule_file_id=rule_file.id, content=rule_file.content))
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
