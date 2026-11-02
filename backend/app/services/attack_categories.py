"""CRS's own attack-category tagging convention - every CRS rule that
represents an actual attack type carries exactly one `attack-*` tag, e.g.
`attack-sqli`, `attack-xss`, `attack-protocol` (confirmed against real
audit log entries, see CLAUDE.md's "Logs page enrichment" section).

Shared between stats_service (category counts/trend) and log_service
(the Logs page's "filter by category" dimension) so both sides agree on
exactly the same tag-to-label mapping - a log entry is "in" a category
if and only if the stats endpoints would have counted it there too.
"""

import re

# Known ones get a human label; anything else falls back to a generic
# "attack-foo-bar" -> "Foo Bar" transform so a future/custom tag still
# shows up sanely instead of being dropped.
CATEGORY_LABELS: dict[str, str] = {
    "attack-sqli": "SQL Injection",
    "attack-xss": "XSS",
    "attack-rce": "Remote Code Execution",
    "attack-lfi": "Local File Inclusion",
    "attack-rfi": "Remote File Inclusion",
    "attack-protocol": "Protocol Enforcement",
    "attack-generic": "Generic Attack",
    "attack-injection-generic": "Generic Injection",
    "attack-injection-php": "PHP Injection",
    "attack-injection-java": "Java Injection",
    "attack-injection-nodejs": "Node.js Injection",
    "attack-disclosure": "Information Disclosure",
    "attack-dos": "Denial of Service",
    "attack-reputation-scanner": "Reputation / Scanner",
    "attack-reputation-ip": "Reputation / Known-bad IP",
}
ATTACK_TAG_RE = re.compile(r"^attack-")


def category_label(tag: str) -> str:
    if tag in CATEGORY_LABELS:
        return CATEGORY_LABELS[tag]
    return ATTACK_TAG_RE.sub("", tag).replace("-", " ").replace("_", " ").title()


def match_category(tags: list[str]) -> set[str]:
    """Every attack category a single rule match belongs to (almost always
    0 or 1, since CRS rules carry one attack-* tag each, but this doesn't
    assume that - a match with two such tags counts toward both)."""
    return {category_label(tag) for tag in tags if ATTACK_TAG_RE.match(tag)}
