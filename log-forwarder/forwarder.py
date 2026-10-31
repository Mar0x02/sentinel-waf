"""Tails the shared ModSecurity audit log volume and forwards each new
transaction to every enabled sink in log-sinks.json (rendered by the
dashboard backend - see app/services/render_service.py), and notifies
every enabled Discord webhook about newly blocked requests. Stdlib only,
on purpose: this is a small sidecar, not worth a dependency footprint.
"""

import json
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOG_DIR = Path("/data/logs")
SINK_CONFIG_PATH = Path("/render/log-sinks/log-sinks.json")
DISCORD_CONFIG_PATH = Path("/render/discord/webhooks.json")
OFFSETS_PATH = Path("/state/offsets.json")
POLL_SECONDS = 2
SINK_RELOAD_EVERY = 5  # in poll cycles
DISCORD_MAX_FIELDS = 10  # Discord embeds allow up to 25; keep messages short


def load_sinks() -> list[dict]:
    try:
        return json.loads(SINK_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_discord_webhooks() -> list[dict]:
    try:
        return json.loads(DISCORD_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_offsets() -> dict[str, int]:
    try:
        return json.loads(OFFSETS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_offsets(offsets: dict[str, int]) -> None:
    OFFSETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSETS_PATH.write_text(json.dumps(offsets))


def is_blocked(entry: dict) -> bool:
    tx = entry.get("transaction", {})
    return tx.get("response", {}).get("http_code") == 403


def syslog_message(entry: dict) -> str:
    tx = entry.get("transaction", {})
    request = tx.get("request", {})
    response = tx.get("response", {})
    messages = tx.get("messages", [])
    rule_ids = ",".join(
        str(m.get("details", {}).get("ruleId")) for m in messages if m.get("details", {}).get("ruleId")
    )
    status = response.get("http_code")
    blocked = "blocked" if is_blocked(entry) else "detected"
    return (
        f"waf[{blocked}] client={tx.get('client_ip')} "
        f"method={request.get('method')} uri={request.get('uri')} "
        f"status={status} rules={rule_ids or '-'}"
    )


def send_to_sink(sink: dict, message: str) -> None:
    # Facility local0 (16), severity info (6): 16*8+6 = 134.
    packet = f"<134>{message}".encode("utf-8", errors="replace")
    try:
        if sink["protocol"] == "tcp":
            with socket.create_connection((sink["host"], sink["port"]), timeout=3) as s:
                s.sendall(packet + b"\n")
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(packet, (sink["host"], sink["port"]))
    except OSError as e:
        print(f"log-forwarder: failed to send to sink {sink.get('name')}: {e}", flush=True)


def _blocked_entry_line(entry: dict) -> str:
    tx = entry.get("transaction", {})
    request = tx.get("request", {})
    messages = tx.get("messages", [])
    first_rule = next((m for m in messages if m.get("details", {}).get("ruleId")), None)
    rule_desc = (
        f"rule {first_rule['details']['ruleId']}: {first_rule.get('message', '')}" if first_rule else "no rule detail"
    )
    method = request.get("method", "?")
    uri = (request.get("uri") or "")[:200]
    return f"**{tx.get('client_ip', '?')}** → `{method} {uri}` - {rule_desc}"


def discord_payload(entries: list[dict]) -> dict:
    # Batched into one message per poll cycle (see main()) specifically to
    # stay well under Discord's ~30 requests/minute per-webhook rate
    # limit even during a burst of blocked traffic - see CLAUDE.md.
    shown = entries[:DISCORD_MAX_FIELDS]
    description = "\n".join(_blocked_entry_line(e) for e in shown)
    if len(entries) > DISCORD_MAX_FIELDS:
        description += f"\n*...and {len(entries) - DISCORD_MAX_FIELDS} more*"
    title = f"🛡️ Sentinel WAF blocked {len(entries)} request{'s' if len(entries) != 1 else ''}"
    return {
        "embeds": [
            {
                "title": title,
                "description": description[:4096],
                "color": 0xED4245,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }


def send_discord(webhook: dict, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook["webhook_url"], data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"log-forwarder: discord webhook {webhook.get('name')} returned {e.code}: {e.read()[:200]}", flush=True)
    except urllib.error.URLError as e:
        print(f"log-forwarder: failed to reach discord webhook {webhook.get('name')}: {e}", flush=True)


def tail_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    size = path.stat().st_size
    if size < offset:
        offset = 0  # file was rotated/truncated
    with path.open("r", errors="replace") as f:
        f.seek(offset)
        data = f.read()
        new_offset = f.tell()
    lines = [line for line in data.splitlines() if line.strip()]
    return lines, new_offset


def main() -> None:
    offsets = load_offsets()
    sinks = load_sinks()
    discord_webhooks = load_discord_webhooks()
    cycle = 0

    while True:
        cycle += 1
        if cycle % SINK_RELOAD_EVERY == 0:
            sinks = load_sinks()
            discord_webhooks = load_discord_webhooks()

        enabled_sinks = [s for s in sinks if s.get("enabled", True)]
        newly_blocked: list[dict] = []

        if AUDIT_LOG_DIR.exists():
            for path in sorted(AUDIT_LOG_DIR.rglob("*")):
                if not path.is_file():
                    continue
                key = str(path)
                lines, new_offset = tail_new_lines(path, offsets.get(key, 0))
                offsets[key] = new_offset
                for line in lines:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = syslog_message(entry)
                    for sink in enabled_sinks:
                        send_to_sink(sink, message)
                    if is_blocked(entry):
                        newly_blocked.append(entry)
            save_offsets(offsets)

        if newly_blocked and discord_webhooks:
            payload = discord_payload(newly_blocked)
            for webhook in discord_webhooks:
                send_discord(webhook, payload)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
