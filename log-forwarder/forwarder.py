"""Tails the shared ModSecurity audit log volume and forwards each new
transaction to every enabled sink in log-sinks.json (rendered by the
dashboard backend - see app/services/render_service.py). Stdlib only, on
purpose: this is a small sidecar, not worth a dependency footprint.
"""

import json
import socket
import time
from pathlib import Path

AUDIT_LOG_DIR = Path("/data/logs")
SINK_CONFIG_PATH = Path("/render/log-sinks/log-sinks.json")
OFFSETS_PATH = Path("/state/offsets.json")
POLL_SECONDS = 2
SINK_RELOAD_EVERY = 5  # in poll cycles


def load_sinks() -> list[dict]:
    try:
        return json.loads(SINK_CONFIG_PATH.read_text())
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


def syslog_message(entry: dict) -> str:
    tx = entry.get("transaction", {})
    request = tx.get("request", {})
    response = tx.get("response", {})
    messages = tx.get("messages", [])
    rule_ids = ",".join(
        str(m.get("details", {}).get("ruleId")) for m in messages if m.get("details", {}).get("ruleId")
    )
    status = response.get("http_code")
    blocked = "blocked" if status == 403 else "detected"
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
    cycle = 0

    while True:
        cycle += 1
        if cycle % SINK_RELOAD_EVERY == 0:
            sinks = load_sinks()

        enabled_sinks = [s for s in sinks if s.get("enabled", True)]
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
            save_offsets(offsets)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
