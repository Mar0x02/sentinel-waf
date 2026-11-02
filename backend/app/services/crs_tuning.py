"""Safely reads/writes the handful of CRS tunables (paranoia level, anomaly
score thresholds) that live as commented-out SecAction blocks inside an
imported rule set's crs-setup.conf. Mirrors the official
coreruleset-docker configure-rules.sh mechanism (same rule IDs, same tx.*
variable names - see configure-rules.v4.conf), but reimplemented here as a
"replace the whole block" operation on RuleFile.content rather than
line-range `ed` edits, since we're rewriting a Python string, not a file
on disk. See CLAUDE.md.

Only four tunables are covered - the ones that matter for day-to-day WAF
operation (reducing false positives / raising sensitivity). CRS has many
more (ALLOWED_METHODS, MAX_FILE_SIZE, etc) available via the Advanced
raw-edit path on the same file, not worth a dedicated form field each.
"""

import re
from dataclasses import dataclass

# CRS's own shipped default values (the ones shown, commented-out, in
# crs-setup.conf.example) - used both as the fallback shown in the UI when
# nothing's been tuned yet, and to know what the file ships with.
DEFAULT_BLOCKING_PARANOIA_LEVEL = 1
DEFAULT_DETECTION_PARANOIA_LEVEL = 1
DEFAULT_INBOUND_ANOMALY_SCORE_THRESHOLD = 5
DEFAULT_OUTBOUND_ANOMALY_SCORE_THRESHOLD = 4


@dataclass
class CrsTuning:
    blocking_paranoia_level: int
    detection_paranoia_level: int
    inbound_anomaly_score_threshold: int
    outbound_anomaly_score_threshold: int


# Matches a (possibly `#`-commented) SecAction block, from the
# `SecAction \` line through to the line that closes the quoted action
# list (ends in `"` with no trailing `\`) - no id requirement embedded in
# the pattern itself (see _find_block for why).
#
# The `$` before `\r?\n?` is load-bearing, not decorative - without it
# this matches the *opening* quote line too (e.g. `#    "id:900000,\`
# has a `"` right after the leading `#    `), so the lazy continuation
# group never needs to run at all and every match truncates to a few
# characters, silently skipping the real block entirely (confirmed: with
# the anchor missing, tuning writes against real CRS content returned 200
# but the file was never actually updated - found by testing a round-trip
# write+read-back, not from reading the regex). This is the exact bug
# documented in tunable_scanner.py's own _BLOCK_RE comment - copy that
# anchor whenever this pattern shape is reused elsewhere.
_BLOCK_RE = re.compile(
    r"[ \t]*#?SecAction\s*\\\r?\n"
    r"(?:[ \t]*#?[^\n]*\\\r?\n)*?"
    r'[ \t]*#?[^\n]*"[ \t]*$\r?\n?',
    re.MULTILINE,
)


def _find_block(content: str, rule_id: str) -> re.Match | None:
    """Finds the (possibly `#`-commented) SecAction block containing
    `id:<rule_id>`. Scans for *any* SecAction-to-closing-quote block first
    via _BLOCK_RE, then checks each one's text for the id as a cheap
    post-hoc substring search - deliberately NOT embedding `id:{rule_id}`
    as a required line inside _BLOCK_RE's own repeated group.

    An earlier version did embed it, and it hung the entire backend
    (confirmed - had to restart the container) the first time this ran
    against content that never contains the id at all: two independent
    lazily-repeated `(?:[^\\n]*\\\\\\r?\\n)*?` groups (one before the
    id-line, one after) both search for a match that doesn't exist, which
    means trying every possible split of how many continuation lines
    belong to each group - exponential in the block's line count. A CRS
    tunable block being searched for its own (present) id usually
    short-circuits fast; Base Tuning's combined ~13-line id:100900 block,
    searched for an id (900000) it never contains, is exactly the
    adversarial case that blows this up. This file-scan-then-substring-
    check approach can't backtrack that way: each candidate block's end is
    found independently of whether the id is present, so it's always
    O(document length) regardless of whether/where a match exists - same
    shape as tunable_scanner._BLOCK_RE, which handles the identical
    "block boundary" problem without this failure mode.
    """
    id_re = re.compile(rf"id:{re.escape(rule_id)}\b")
    for match in _BLOCK_RE.finditer(content):
        if id_re.search(match.group(0)):
            return match
    return None


def _extract_int(content: str, rule_id: str, var_name: str, default: int) -> int:
    match = _find_block(content, rule_id)
    if not match:
        return default
    block = match.group(0)
    # Only trust a value from a line that isn't commented out - a still-
    # commented block means "not tuned yet", fall back to the default.
    value_match = re.search(rf"^[ \t]*setvar:tx\.{var_name}=(\d+)", block, re.MULTILINE)
    return int(value_match.group(1)) if value_match else default


def read_tuning(setup_content: str) -> CrsTuning:
    return CrsTuning(
        blocking_paranoia_level=_extract_int(
            setup_content, "900000", "blocking_paranoia_level", DEFAULT_BLOCKING_PARANOIA_LEVEL
        ),
        detection_paranoia_level=_extract_int(
            setup_content, "900001", "detection_paranoia_level", DEFAULT_DETECTION_PARANOIA_LEVEL
        ),
        inbound_anomaly_score_threshold=_extract_int(
            setup_content, "900110", "inbound_anomaly_score_threshold", DEFAULT_INBOUND_ANOMALY_SCORE_THRESHOLD
        ),
        outbound_anomaly_score_threshold=_extract_int(
            setup_content, "900110", "outbound_anomaly_score_threshold", DEFAULT_OUTBOUND_ANOMALY_SCORE_THRESHOLD
        ),
    )


def _replace_block(content: str, rule_id: str, new_block: str) -> str:
    match = _find_block(content, rule_id)
    if match:
        return content[: match.start()] + new_block + content[match.end() :]
    # Unexpected format (not a stock CRS setup file) - don't guess at
    # surgery, just append an active block. The id is unique, so this
    # can't collide with whatever (if anything) didn't match above.
    return content.rstrip() + "\n\n" + new_block


def write_tuning(setup_content: str, tuning: CrsTuning) -> str:
    content = setup_content
    content = _replace_block(
        content,
        "900000",
        f'SecAction \\\n'
        f'    "id:900000,\\\n'
        f"    phase:1,\\\n"
        f"    pass,\\\n"
        f"    t:none,\\\n"
        f"    nolog,\\\n"
        f"    tag:'OWASP_CRS',\\\n"
        f'    setvar:tx.blocking_paranoia_level={tuning.blocking_paranoia_level}"\n',
    )
    content = _replace_block(
        content,
        "900001",
        f'SecAction \\\n'
        f'    "id:900001,\\\n'
        f"    phase:1,\\\n"
        f"    pass,\\\n"
        f"    t:none,\\\n"
        f"    nolog,\\\n"
        f"    tag:'OWASP_CRS',\\\n"
        f'    setvar:tx.detection_paranoia_level={tuning.detection_paranoia_level}"\n',
    )
    content = _replace_block(
        content,
        "900110",
        f'SecAction \\\n'
        f'    "id:900110,\\\n'
        f"    phase:1,\\\n"
        f"    pass,\\\n"
        f"    t:none,\\\n"
        f"    nolog,\\\n"
        f"    tag:'OWASP_CRS',\\\n"
        f"    setvar:tx.inbound_anomaly_score_threshold={tuning.inbound_anomaly_score_threshold},\\\n"
        f'    setvar:tx.outbound_anomaly_score_threshold={tuning.outbound_anomaly_score_threshold}"\n',
    )
    return content
