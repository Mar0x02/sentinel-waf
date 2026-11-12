"""In-memory lockout for repeated failed /api/auth/login attempts, keyed
by client IP. No DB table, no Redis - same trust model as every other
in-memory-only state in this project (e.g. acme_service._PENDING): lost
on a backend restart, which just means a locked-out IP gets a clean slate
a bit early. Fine for the self-hosted, not-directly-internet-exposed
tool CLAUDE.md already describes - this is what "no login throttling"
there was waiting on.
"""

import time

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 5 * 60
LOCKOUT_SECONDS = 15 * 60

# ip -> {"count", "window_started_at", "locked_until"}, all monotonic-clock
# seconds. Never pruned - a handful of floats per distinct attacking IP for
# the life of the process isn't worth a cleanup pass.
_state: dict[str, dict[str, float]] = {}


def seconds_until_unlocked(ip: str) -> float:
    entry = _state.get(ip)
    if entry is None:
        return 0.0
    remaining = entry["locked_until"] - time.monotonic()
    return remaining if remaining > 0 else 0.0


def record_failure(ip: str) -> None:
    now = time.monotonic()
    entry = _state.get(ip)
    if entry is None or now - entry["window_started_at"] > WINDOW_SECONDS:
        entry = {"count": 0, "window_started_at": now, "locked_until": 0.0}
        _state[ip] = entry
    entry["count"] += 1
    if entry["count"] >= MAX_ATTEMPTS:
        entry["locked_until"] = now + LOCKOUT_SECONDS


def record_success(ip: str) -> None:
    _state.pop(ip, None)
