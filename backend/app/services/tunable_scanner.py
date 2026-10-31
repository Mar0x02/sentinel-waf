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
