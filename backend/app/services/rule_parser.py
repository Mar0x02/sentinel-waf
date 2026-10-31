import re
from dataclasses import dataclass

# ModSecurity rule syntax isn't parsed as a full grammar here - this is a
# best-effort splitter used only to populate the Rule table for listing /
# search / individual toggling in the UI. Rendering never reconstructs a
# file from these rows (see models.Rule docstring), so an imperfect split
# only affects what the UI shows, never what ModSecurity actually runs.
_TOP_LEVEL_RE = re.compile(r"^\s*Sec(Rule|Action)\b", re.IGNORECASE)
_ID_RE = re.compile(r"id:'?(\d+)'?")
_MSG_RE = re.compile(r"msg:'([^']*)'")
_CHAIN_RE = re.compile(r"(?:^|,)\s*chain\b", re.IGNORECASE)
_HAS_DIRECTIVE_RE = re.compile(r"\bSec(Rule|Action)\b", re.IGNORECASE)


@dataclass
class ParsedRule:
    rule_id: str | None
    message: str | None
    raw_snippet: str
    order_index: int


def _logical_blocks(content: str) -> list[list[str]]:
    """Group raw lines into logical statements, joining `\\`-continuations."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in content.splitlines():
        current.append(line)
        if line.rstrip().endswith("\\"):
            continue
        blocks.append(current)
        current = []
    if current:
        blocks.append(current)
    return blocks


def parse_rules(content: str) -> list[ParsedRule]:
    results: list[ParsedRule] = []
    pending: list[str] = []
    chain_open = False
    order_index = 0

    def flush() -> None:
        nonlocal pending, order_index
        if not pending:
            return
        text = "\n".join(pending)
        joined = " ".join(line.rstrip("\\").strip() for line in pending)
        if _HAS_DIRECTIVE_RE.search(text):
            id_match = _ID_RE.search(joined)
            msg_match = _MSG_RE.search(joined)
            results.append(
                ParsedRule(
                    rule_id=id_match.group(1) if id_match else None,
                    message=msg_match.group(1) if msg_match else None,
                    raw_snippet=text,
                    order_index=order_index,
                )
            )
            order_index += 1
        pending = []

    for block in _logical_blocks(content):
        joined_block = " ".join(line.rstrip("\\").strip() for line in block)
        starts_new_rule = bool(_TOP_LEVEL_RE.match(block[0])) and not chain_open
        if starts_new_rule:
            flush()
            pending = list(block)
        else:
            pending.extend(block)
        chain_open = bool(_CHAIN_RE.search(joined_block))
    flush()
    return results
