from collections import Counter

from app.config import Settings
from app.schemas.stats import IpCount, RuleCount, SeverityCount, StatsSummary, TrendPoint
from app.services.log_service import load_entries


def get_summary(settings: Settings) -> StatsSummary:
    entries = load_entries(settings)
    blocked = sum(1 for e in entries if e.blocked)
    detected = sum(1 for e in entries if e.matches and not e.blocked)
    unique_ips = {e.client_ip for e in entries if e.client_ip}
    return StatsSummary(
        total_requests=len(entries),
        total_blocked=blocked,
        total_detected=detected,
        unique_ips=len(unique_ips),
    )


def get_top_rules(settings: Settings, limit: int = 10) -> list[RuleCount]:
    entries = load_entries(settings)
    counter: Counter[str] = Counter()
    messages: dict[str, str | None] = {}
    for entry in entries:
        for match in entry.matches:
            if not match.rule_id:
                continue
            counter[match.rule_id] += 1
            messages.setdefault(match.rule_id, match.message)
    return [
        RuleCount(rule_id=rule_id, message=messages.get(rule_id), count=count)
        for rule_id, count in counter.most_common(limit)
    ]


def get_top_ips(settings: Settings, limit: int = 10) -> list[IpCount]:
    entries = load_entries(settings)
    counter = Counter(e.client_ip for e in entries if e.client_ip)
    return [IpCount(ip=ip, count=count) for ip, count in counter.most_common(limit)]


def get_severity_breakdown(settings: Settings) -> list[SeverityCount]:
    entries = load_entries(settings)
    counter: Counter[str] = Counter()
    for entry in entries:
        for match in entry.matches:
            if match.severity:
                counter[match.severity] += 1
    return [SeverityCount(severity=sev, count=count) for sev, count in counter.most_common()]


def get_trend(settings: Settings) -> list[TrendPoint]:
    """Hourly request/blocked counts, bucketed as 'YYYY-MM-DD HH:00'."""
    entries = load_entries(settings)
    totals: Counter[str] = Counter()
    blocked_counts: Counter[str] = Counter()
    for entry in entries:
        if not entry.timestamp:
            continue
        bucket = entry.timestamp.strftime("%Y-%m-%d %H:00")
        totals[bucket] += 1
        if entry.blocked:
            blocked_counts[bucket] += 1

    return [
        TrendPoint(bucket=bucket, total=total, blocked=blocked_counts.get(bucket, 0))
        for bucket, total in sorted(totals.items())
    ]
