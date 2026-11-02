"""Best-effort linter that cross-references ModSecurity TX-collection
variable reads (``TX:name`` / ``%{TX.name}``) against writes
(``setvar:tx.name=...``) across every currently *enabled* rule file in
every currently *enabled* rule set - not just the file being edited,
since TX is one collection shared across every Include'd file for the
life of a transaction (a var defined in e.g. crs-setup.conf is visible to
every rule file loaded after it).

This catches the easy-to-make mistake the dashboard's rule editor can't
otherwise warn about: referencing ``tx.my_var`` in a rule's condition or
action without ever having added a ``SecAction`` that defines it (typo,
or just forgetting the setvar).

Advisory only, same "best-effort, not a grammar parser" posture as
rule_parser.py (reused here to split content into logical rule blocks so
each warning can be tagged with the rule id that references the
variable) - this never blocks a save. It can't be order/phase-aware
without a real ModSecurity grammar parser (a var defined later in load
order than where it's read would still read as "defined" here), so a
clean lint result is a helpful signal, not a correctness guarantee - the
container-level ``nginx -t`` before reload remains the only real gate,
same as everywhere else in this project. See CLAUDE.md.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.default_base_tuning import KNOWN_DEFAULTS
from app.models import FileKind, Rule, RuleFile, RuleSet
from app.services import tunable_scanner
from app.services.importer import BASE_TUNING_RULE_SET_SLUG
from app.services.rule_parser import parse_rules

# Starting point for auto-suggested new tunable IDs (see _find_fix's
# "create a new one" path) - comfortably above Base Tuning's own
# 100900/100950/100960 and a typical custom rule's low 100xxx IDs, while
# staying inside the 100000-199999 range reserved for Sentinel-authored
# content (never CRS's own 900000-999999).
_AUTO_FIX_ID_START = 101000

# setvar:tx.name=... / setvar:'tx.name=...' defines (or increments) a TX
# variable. setvar:!tx.name *removes* one instead - excluded via the
# negative lookahead so it's never mistaken for a definition.
_SETVAR_WRITE_RE = re.compile(r"setvar:'?(?!!)tx\.([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

# TX:name (rule variable syntax) or %{TX.name} (macro expansion in msg,
# logdata, setvar right-hand sides, etc).
_TX_READ_RE = re.compile(r"(?:TX:|%\{TX\.)([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)

_COMMENTED_LINE_RE = re.compile(r"^[ \t]*#")

# setvar:ip.name=... / setvar:session.name=... / setvar:user.name=... -
# persistent collections that (unlike TX, which is per-transaction and
# needs no setup) require an explicit initcol:<collection>=<key> somewhere
# in phase:1 before they'll actually persist across requests. Writing to
# one without that is a silent no-op across requests, not an error -
# ModSecurity doesn't warn either, which is exactly why this needed its
# own check (see CLAUDE.md-equivalent reasoning in lint_collection_init).
_COLLECTION_SETVAR_RE = re.compile(r"setvar:'?(?!!)(ip|session|user)\.([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_INITCOL_RE = re.compile(r"\binitcol:(ip|session|user)\b", re.IGNORECASE)

# A var being *incremented* (setvar:x.name=+...) implies it's meant to be
# a running counter read back later by some other rule's condition - as
# opposed to a one-shot setvar:x.name=<value> assignment, which is
# routinely write-only (e.g. a scaffolding default). Only the increment
# form is checked for "is this ever read as a match target" - a plain
# assignment is written off as deliberately one-way.
_INCREMENT_WRITE_RE = re.compile(r"setvar:'?(?!!)(tx|ip|session|user)\.([A-Za-z_][A-Za-z0-9_]*)=\+", re.IGNORECASE)
# Any read of a collection member counts as "evaluated" - either as a
# SecRule match target (`SecRule IP:FAILED_LOGINS "@gt 3"`, the leading
# `&` presence/count form included) or a %{...} macro expansion anywhere,
# including inside *another* setvar's right-hand side. The macro form is
# deliberately included, not just match targets - caught by testing a
# real false positive: CRS's own aggregation pattern
# (setvar:tx.inbound_anomaly_score=+%{tx.inbound_anomaly_score_pl1}, see
# default_base_tuning.py's id:100950) reads pl1 purely via macro
# expansion, never as a literal match target, and a match-target-only
# definition of "evaluated" flagged it as an unused counter even though
# it's exactly the intended multi-hop pattern (pl1 feeds the aggregate,
# the aggregate is what the final id:100960 rule actually checks).
_MATCH_TARGET_RE = re.compile(r"&?(TX|IP|SESSION|USER):([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_MACRO_READ_RE = re.compile(r"%\{(TX|IP|SESSION|USER)\.([A-Za-z_][A-Za-z0-9_]*)\}", re.IGNORECASE)


def _writes_in(text: str) -> set[str]:
    """setvar writes found on *uncommented* lines only. A naive whole-text
    regex scan would also match a setvar sitting inside a still-commented
    (inactive) tunable block - e.g. crs-setup.conf ships every one of its
    ~24 tunables commented out by default (see tunable_scanner.py) - which
    would make the linter wrongly treat a var as "defined" when Modsecurity
    never actually executes that line. Caught by testing: once CRS was
    enabled, a var that only existed in a still-commented block (e.g.
    early_blocking's tx var in id:900120) produced zero warnings instead of
    the expected one. CRS's own convention comments every line of a
    deactivated block (see tunable_scanner.apply_tunable), so a per-line
    "skip lines starting with #" filter is enough - no block-aware parsing
    needed.
    """
    return {
        m.lower()
        for line in text.splitlines()
        if not _COMMENTED_LINE_RE.match(line)
        for m in _SETVAR_WRITE_RE.findall(line)
    }


def _is_builtin(name: str) -> bool:
    # Numbered regex capture groups (tx.0..tx.9, populated automatically by
    # the last @rx/@pm match) are never written via setvar - excluding
    # anything purely numeric avoids false-positives on those.
    return name.isdigit()


@dataclass
class TunableFix:
    """Either points at a specific commented-out (inactive) tunable block
    that, once activated, would define the warning's variable (is_new=
    False - a real match found by scanning every enabled rule set's setup
    file with tunable_scanner), or proposes creating a brand-new one in
    Base Tuning with a safe placeholder value of "0" when no existing
    tunable anywhere defines it at all (is_new=True) - the UI offers this
    as "add it" rather than "activate it" accordingly. Either way this is
    surfaced for a one-click fix instead of a dead-end warning.

    init_collection is a third, distinct fix shape: set only for
    "uninitialized_collection" warnings, where there's no tx.*/value to
    assign at all - the fix is a single fixed directive
    (initcol:<collection>=%{REMOTE_ADDR}), not a setvar. The UI/API use
    this to call a different endpoint (raw action, not a tunable value).
    """

    rule_set_id: int
    rule_set_name: str
    tunable_rule_id: str
    variables: dict[str, str]
    is_new: bool = False
    init_collection: str | None = None


@dataclass
class TxVarWarning:
    variable: str
    rule_id: str | None
    snippet: str
    fix: TunableFix | None = None
    # "undefined_var" (default) - a tx.* read with no setvar anywhere.
    # "uninitialized_collection" - an ip./session./user. setvar with no
    #   matching initcol anywhere, so it won't persist across requests.
    # "unused_counter" - a tx./ip./session./user. var incremented
    #   (setvar:...=+...) but never used as a SecRule match target
    #   anywhere active, so nothing ever acts on it. No fix offered - we
    #   can't guess the intended threshold/action.
    kind: str = "undefined_var"


def _active_rule_file_contents(db: Session, exclude_rule_file_id: int | None) -> list[str]:
    """Content of every enabled rule file in every enabled rule set - the
    scope that actually matters for TX, which isn't scoped per-file."""
    query = (
        db.query(RuleFile.id, RuleFile.content)
        .join(RuleSet, RuleFile.rule_set_id == RuleSet.id)
        .filter(RuleFile.enabled.is_(True), RuleSet.enabled.is_(True))
    )
    return [content for file_id, content in query.all() if file_id != exclude_rule_file_id]


def _find_fix(db: Session, variable_lower: str) -> TunableFix | None:
    """Looks for a currently-inactive (commented-out) tunable block, in any
    enabled rule set's setup file, whose setvar would define `variable`.
    Scans every enabled rule set regardless of whether it's the one the
    linted content belongs to - a tunable commonly lives in a different
    rule set's crs-setup.conf than the custom rule referencing it. Returns
    the first match; in practice this is only ambiguous if two rule sets
    both define the exact same tx var name, which would itself be a
    pre-existing collision outside this feature's scope.
    """
    setup_files = (
        db.query(RuleFile.content, RuleSet.id, RuleSet.name)
        .join(RuleSet, RuleFile.rule_set_id == RuleSet.id)
        .filter(RuleFile.file_kind == FileKind.setup, RuleFile.enabled.is_(True), RuleSet.enabled.is_(True))
        .all()
    )
    for content, rule_set_id, rule_set_name in setup_files:
        for group in tunable_scanner.scan_tunables(content):
            if group.is_active:
                continue
            if any(name.lower() == variable_lower for name in group.variables):
                return TunableFix(
                    rule_set_id=rule_set_id,
                    rule_set_name=rule_set_name,
                    tunable_rule_id=group.rule_id,
                    variables=group.variables,
                )

    # No existing tunable (active or not) defines this var anywhere -
    # offer to create a brand-new one in Base Tuning instead, rather than
    # leaving a dead-end warning. Never offered if Base Tuning somehow
    # isn't seeded yet (shouldn't happen post-startup, but this function
    # has no business crashing lint over it).
    base_tuning = db.query(RuleSet).filter(RuleSet.slug == BASE_TUNING_RULE_SET_SLUG).first()
    if base_tuning is None:
        return None
    return TunableFix(
        rule_set_id=base_tuning.id,
        rule_set_name=base_tuning.name,
        tunable_rule_id=_next_free_rule_id(db),
        variables={variable_lower: KNOWN_DEFAULTS.get(variable_lower, "0")},
        is_new=True,
    )


def _next_free_rule_id(db: Session) -> str:
    existing = {rid for (rid,) in db.query(Rule.rule_id).filter(Rule.rule_id.isnot(None)).all()}
    candidate = _AUTO_FIX_ID_START
    while str(candidate) in existing:
        candidate += 1
    return str(candidate)


def _uncommented(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _COMMENTED_LINE_RE.match(line))


def _collection_init_fix(db: Session, collection: str) -> TunableFix | None:
    base_tuning = db.query(RuleSet).filter(RuleSet.slug == BASE_TUNING_RULE_SET_SLUG).first()
    if base_tuning is None:
        return None
    return TunableFix(
        rule_set_id=base_tuning.id,
        rule_set_name=base_tuning.name,
        tunable_rule_id=_next_free_rule_id(db),
        variables={},
        is_new=True,
        init_collection=collection,
    )


def lint_collection_init(db: Session, content: str, exclude_rule_file_id: int | None = None) -> list[TxVarWarning]:
    """Warns about setvar:ip.*/session.*/user.* with no matching
    initcol:<collection> anywhere in the active config - unlike TX (which
    needs no setup), these collections silently fail to persist across
    requests without one. Caught from a real custom rule: a brute-force
    lockout counter (setvar:ip.outbound_failed_login=+1) with no initcol
    anywhere, meaning the counter can never actually accumulate across the
    multiple failed-login requests it's supposed to be counting.

    IMPORTANT caveat, confirmed by testing (ModSecurity debug log at
    SecDebugLogLevel 9, real requests through the live WAF): even with
    initcol correctly added, this project's engine (libmodsecurity3 /
    ModSecurity v3, the nginx connector) does NOT actually persist ip/
    session/user collections across requests at all. Every single
    request's initcol log line read "Collection `ip' initialized with
    value: ..." - never "loaded existing collection" - and SecDataDir
    stayed completely empty (0 files) even after multiple "Saving
    variable" log lines. Two consecutive requests from the same IP both
    logged "Saving variable: IP:outbound_failed_login with value: 1" -
    the second one should have been 2 if persistence actually worked.
    This is a known maturity gap in libmodsecurity3 versus the original
    mod_security2 (Apache) implementation, not a bug in this project's
    rendering or rule-writing. The warning/fix this function offers still
    has value (initcol is correct ModSecurity practice in general, and a
    future engine upgrade could fix persistence) but don't expect a
    cross-request counter built this way to actually work on this stack
    today - recommend per-site rate limiting (render_service.render_sites'
    limit_req/limit_conn, Sites page) for anything that needs to track
    abuse across multiple requests from the same IP.
    """
    other_contents = _active_rule_file_contents(db, exclude_rule_file_id)
    initialized = {m.group(1).lower() for text in (*other_contents, content) for m in _INITCOL_RE.finditer(_uncommented(text))}

    warnings: list[TxVarWarning] = []
    seen: set[tuple[str, str | None]] = set()
    for rule in parse_rules(content):
        for collection, name in _COLLECTION_SETVAR_RE.findall(_uncommented(rule.raw_snippet)):
            lcollection = collection.lower()
            if lcollection in initialized:
                continue
            key = (lcollection, rule.rule_id)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(
                TxVarWarning(
                    variable=f"{lcollection}.{name}",
                    rule_id=rule.rule_id,
                    snippet=rule.raw_snippet.strip()[:200],
                    fix=_collection_init_fix(db, lcollection),
                    kind="uninitialized_collection",
                )
            )
    return warnings


def lint_unused_counters(db: Session, content: str, exclude_rule_file_id: int | None = None) -> list[TxVarWarning]:
    """Warns about a var that's incremented (setvar:x.name=+...) but never
    read back anywhere active - neither as a rule's match target nor
    inside a %{...} macro (e.g. feeding another setvar's aggregation) -
    bookkeeping with no actuator, the same class of mistake as a custom
    rule using `block` with no SecDefaultAction to resolve it against,
    just for a counter instead of an anomaly score. No fix offered:
    there's no way to guess what threshold/action was intended.
    """
    other_contents = _active_rule_file_contents(db, exclude_rule_file_id)
    evaluated: set[tuple[str, str]] = set()
    for text in (*other_contents, content):
        uncommented = _uncommented(text)
        evaluated.update((m.group(1).lower(), m.group(2).lower()) for m in _MATCH_TARGET_RE.finditer(uncommented))
        evaluated.update((m.group(1).lower(), m.group(2).lower()) for m in _MACRO_READ_RE.finditer(uncommented))

    warnings: list[TxVarWarning] = []
    seen: set[tuple[str, str, str | None]] = set()
    for rule in parse_rules(content):
        for collection, name in _INCREMENT_WRITE_RE.findall(_uncommented(rule.raw_snippet)):
            lcollection, lname = collection.lower(), name.lower()
            if (lcollection, lname) in evaluated:
                continue
            key = (lcollection, lname, rule.rule_id)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(
                TxVarWarning(
                    variable=f"{lcollection}.{name}",
                    rule_id=rule.rule_id,
                    snippet=rule.raw_snippet.strip()[:200],
                    fix=None,
                    kind="unused_counter",
                )
            )
    return warnings


def lint_tx_vars(db: Session, content: str, exclude_rule_file_id: int | None = None) -> list[TxVarWarning]:
    """Warn about every tx.<name> that `content` reads but that no enabled
    rule file anywhere in the active configuration (including `content`
    itself) ever defines via setvar."""
    other_contents = _active_rule_file_contents(db, exclude_rule_file_id)
    defined = set()
    for text in (*other_contents, content):
        defined.update(_writes_in(text))

    warnings: list[TxVarWarning] = []
    seen: set[tuple[str, str | None]] = set()
    for rule in parse_rules(content):
        for name in _TX_READ_RE.findall(rule.raw_snippet):
            lname = name.lower()
            if _is_builtin(lname) or lname in defined:
                continue
            key = (lname, rule.rule_id)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(
                TxVarWarning(
                    variable=name,
                    rule_id=rule.rule_id,
                    snippet=rule.raw_snippet.strip()[:200],
                    fix=_find_fix(db, lname),
                )
            )
    return warnings
