"""Generic scanner for ModSecurity "tunable" blocks - commented-or-not
`SecAction` statements that carry an `id:` and one or more
`setvar:tx.X=Y` assignments. This is the authoring convention CRS uses for
every one of its ~24 setup-time knobs (not just the 4 covered by
app.services.crs_tuning's dedicated paranoia/anomaly form), and isn't
CRS-specific - any other imported rule package's setup file that follows
the same convention is scanned the same way, with zero per-vendor
hardcoding. See CLAUDE.md.

Unlike crs_tuning.py (which regenerates a handful of known blocks from a
template), this edits matched blocks **in place**: only the targeted
setvar value(s) and the comment prefix change, everything else in the
block (phase, tag, ver, unrelated setvars) is preserved verbatim. That's
deliberate - for an arbitrary, not-specifically-known block, surgical
in-place editing is far safer than reconstructing it from scratch.
"""

import re
from dataclasses import dataclass, field

_BLOCK_RE = re.compile(
    r'[ \t]*#?SecAction\s*\\\r?\n'
    r'(?:[ \t]*#?[^\n]*\\\r?\n)*?'
    # The closing line must end the quoted action list - "$" (MULTILINE)
    # forces this to actually reach end-of-line, not just the first `"`
    # it finds (which would otherwise match mid-line, e.g. on the
    # `#    "id:900000,\` line that opens every block's action list and
    # is NOT the closing line). Confirmed this was a real bug: without
    # the anchor, every match truncated to 19 characters.
    r'[ \t]*#?[^\n]*"[ \t]*$\r?\n?',
    re.MULTILINE,
)
_ID_RE = re.compile(r"id:'?(\d+)")
_SETVAR_RE = re.compile(r"setvar:'?tx\.([A-Za-z0-9_]+)=([^,'\"]+)")
_IS_COMMENTED_RE = re.compile(r"^[ \t]*#")
_PRECEDING_COMMENT_RE = re.compile(r"^[ \t]*#\s*(\S.*\S|\S)[ \t]*$")


@dataclass
class TunableGroup:
    rule_id: str
    description: str | None
    is_active: bool
    variables: dict[str, str] = field(default_factory=dict)


def scan_tunables(content: str, exclude_rule_ids: set[str] = frozenset()) -> list[TunableGroup]:
    groups: list[TunableGroup] = []
    seen_ids: set[str] = set()
    lines = content.splitlines()
    line_offsets = []
    pos = 0
    for line in lines:
        line_offsets.append(pos)
        pos += len(line) + 1

    for match in _BLOCK_RE.finditer(content):
        block = match.group(0)
        id_match = _ID_RE.search(block)
        setvars = _SETVAR_RE.findall(block)
        if not id_match or not setvars:
            continue
        rule_id = id_match.group(1)
        if rule_id in exclude_rule_ids or rule_id in seen_ids:
            continue
        seen_ids.add(rule_id)

        first_line = block.splitlines()[0]
        is_active = not _IS_COMMENTED_RE.match(first_line)

        # Best-effort: the single plain comment line right before this
        # block, if any (CRS's own setup file always documents a tunable
        # this way - "Uncomment this rule to change the default:" etc).
        # Not guaranteed for non-CRS setup files; falls back to None.
        description = None
        line_no = content.count("\n", 0, match.start())
        for back in range(1, 4):
            idx = line_no - back
            if idx < 0:
                break
            candidate = lines[idx]
            if not candidate.strip():
                continue
            comment_match = _PRECEDING_COMMENT_RE.match(candidate)
            if comment_match:
                description = comment_match.group(1)
            break

        groups.append(
            TunableGroup(
                rule_id=rule_id,
                description=description,
                is_active=is_active,
                variables={name: value.strip() for name, value in setvars},
            )
        )

    return groups


def _find_block_span(content: str, rule_id: str) -> tuple[int, int] | None:
    for match in _BLOCK_RE.finditer(content):
        if _ID_RE.search(match.group(0)) and _ID_RE.search(match.group(0)).group(1) == rule_id:
            return match.start(), match.end()
    return None


def apply_tunable(content: str, rule_id: str, variables: dict[str, str], active: bool) -> str:
    """Surgically edits the block for `rule_id` in place: updates each
    given variable's value (leaving any other setvar in the block
    untouched), and comments/uncomments every line of the block to match
    `active`. Raises ValueError if the block isn't found - callers should
    scan first and only offer edits for blocks that actually exist.
    """
    span = _find_block_span(content, rule_id)
    if span is None:
        raise ValueError(f"No tunable block found for id:{rule_id}")
    start, end = span
    block = content[start:end]

    for name, value in variables.items():
        pattern = re.compile(rf"(setvar:'?tx\.{re.escape(name)}=)[^,'\"]+")
        if pattern.search(block):
            block = pattern.sub(lambda m: m.group(1) + value, block, count=1)

    new_lines = []
    for line in block.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        indent = line[: len(line) - len(stripped)]
        is_commented = stripped.startswith("#")
        body = stripped[1:] if is_commented else stripped
        if active:
            new_lines.append(indent + body)
        else:
            new_lines.append(indent + "#" + body)
    new_block = "".join(new_lines)

    return content[:start] + new_block + content[end:]


def add_raw_action(content: str, rule_id: str, phase: int, actions: list[str]) -> str:
    """Appends a brand-new, already-active SecAction block with arbitrary
    actions - not necessarily setvar:tx.X=Y, unlike add_tunable(). Used
    for fixes that aren't a tx.* value assignment, e.g.
    initcol:ip=%{REMOTE_ADDR} (see tx_var_linter.py's
    "uninitialized_collection" warning)."""
    action_list = ",\\\n    ".join(actions)
    block = f'\nSecAction \\\n    "id:{rule_id},\\\n    phase:{phase},\\\n    pass,\\\n    nolog,\\\n    {action_list}"\n'
    return content.rstrip("\n") + "\n" + block


def add_tunable(content: str, rule_id: str, variables: dict[str, str], phase: int = 1) -> str:
    """Appends a brand-new, already-active SecAction block defining
    `variables` via setvar - for a tx.* var that doesn't exist *anywhere*
    yet, as opposed to apply_tunable() which edits an existing block in
    place. Used for the Base Tuning rule set when a custom rule references
    a var with no existing (even inactive) tunable to activate - see
    tx_var_linter.py's "create a new one" fix path. Caller is responsible
    for picking a rule_id that doesn't collide with anything else active.
    """
    setvars = ",\\\n    ".join(f"setvar:tx.{name}={value}" for name, value in variables.items())
    block = f'\nSecAction \\\n    "id:{rule_id},\\\n    phase:{phase},\\\n    pass,\\\n    nolog,\\\n    t:none,\\\n    {setvars}"\n'
    return content.rstrip("\n") + "\n" + block


def sync_from_source(source_content: str, target_content: str) -> tuple[str, list[str]]:
    """Like carry_over_tunables, but matches purely by *variable name*
    across every active tunable in `source_content`, not by matching rule
    id - needed when source and target don't share the same id scheme.
    Confirmed by testing this is NOT the same case carry_over_tunables
    handles: Base Tuning covers paranoia/severity/threshold vars in one
    combined id:100900 block, while CRS's own crs-setup.conf splits the
    exact same variable names across four separate ids
    (900000/900001/900100/900110) - id-based matching found zero overlap
    between them even though every variable name matched.

    Builds a flat name->value map from every active source tunable, then
    for each target block (commented or not) where *every* variable name
    is covered by that map, applies those values and activates it. A
    target block with only some of its names covered is skipped entirely
    - same "never guess" principle as carry_over_tunables, a half-filled
    block is worse than an unfilled one.
    """
    source_values: dict[str, str] = {}
    for group in scan_tunables(source_content):
        if group.is_active:
            for name, value in group.variables.items():
                source_values[name.lower()] = value

    applied: list[str] = []
    for group in scan_tunables(target_content):
        names = list(group.variables.keys())
        if not names or any(name.lower() not in source_values for name in names):
            continue
        values = {name: source_values[name.lower()] for name in names}
        target_content = apply_tunable(target_content, group.rule_id, values, active=True)
        applied.append(group.rule_id)

    return target_content, applied


def carry_over_tunables(old_content: str, new_content: str) -> tuple[str, list[str]]:
    """For migrating hand-tuning forward onto a freshly imported setup
    file (e.g. upgrading CRS 4.29 -> 4.30): copies every ACTIVE tunable's
    values from `old_content` onto the matching block in `new_content`,
    activating it there too.

    Only applies when the id AND every variable name match exactly between
    old and new - a different CRS major version can reuse the same id for
    a renamed variable (confirmed: CRS 3.x's id:900000 sets
    tx.paranoia_level, CRS 4.x's id:900000 sets
    tx.blocking_paranoia_level - same id, different var). A mismatch is
    always skipped rather than guessed at, so this never forces a value
    onto an unrelated variable - worst case, a tunable simply isn't
    carried over and keeps the new version's shipped default.
    """
    old_groups = {g.rule_id: g for g in scan_tunables(old_content) if g.is_active}
    new_groups = {g.rule_id: g for g in scan_tunables(new_content)}

    applied: list[str] = []
    for rule_id, old_group in old_groups.items():
        new_group = new_groups.get(rule_id)
        if new_group is None:
            continue
        if {k.lower() for k in old_group.variables} != {k.lower() for k in new_group.variables}:
            continue
        new_content = apply_tunable(new_content, rule_id, old_group.variables, active=True)
        applied.append(rule_id)

    return new_content, applied
