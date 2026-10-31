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


def _block_regex(rule_id: str) -> re.Pattern:
    """Matches a (possibly `#`-commented) SecAction block containing
    `id:<rule_id>`, from the `SecAction \\` line through to the line that
    closes the quoted action list (ends in `"` with no trailing `\\`).
    Works whether the block is still commented (vendor default) or was
    already uncommented by a previous tuning save.
    """
    return re.compile(
        rf'[ \t]*#?SecAction\s*\\\r?\n'
        rf'(?:[ \t]*#?[^\n]*\\\r?\n)*?'
        rf'[ \t]*#?[^\n]*id:{re.escape(rule_id)}\b[^\n]*\\\r?\n'
        rf'(?:[ \t]*#?[^\n]*\\\r?\n)*?'
        rf'[ \t]*#?[^\n]*"[ \t]*\r?\n?',
        re.MULTILINE,
    )


def _extract_int(content: str, rule_id: str, var_name: str, default: int) -> int:
    match = _block_regex(rule_id).search(content)
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
    pattern = _block_regex(rule_id)
    match = pattern.search(content)
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
