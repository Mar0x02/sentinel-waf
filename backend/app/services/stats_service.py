from collections import Counter
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.schemas.stats import (
    CategoryCount,
    CategorySeries,
    CategoryTrend,
    CountryCount,
    IpCount,
    RuleCount,
    SeverityCount,
    StatsSummary,
    TrendPoint,
)
from app.services import geoip_service
from app.services.attack_categories import ATTACK_TAG_RE, category_label
from app.services.country_centroids import COUNTRY_CENTROIDS
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


def get_top_categories(settings: Settings, limit: int = 10) -> list[CategoryCount]:
    """Ranks matches by CRS attack category (attack-sqli, attack-xss, ...)
    rather than by individual rule ID - several rule IDs commonly share one
    category (e.g. 941100/941110/941160/941390 are all attack-xss), which
    get_top_rules alone can't show grouped. A match with no `attack-*` tag
    (e.g. the anomaly-score summary rule, which only carries
    `anomaly-evaluation`) contributes to no category - it's not itself an
    attack type, just a meta-rule, same reasoning as get_top_rules
    skipping matches with no rule_id.
    """
    entries = load_entries(settings)
    counter: Counter[str] = Counter()
    for entry in entries:
        for match in entry.matches:
            for tag in match.tags:
                if ATTACK_TAG_RE.match(tag):
                    counter[category_label(tag)] += 1
    return [CategoryCount(category=category, count=count) for category, count in counter.most_common(limit)]


def get_category_trend(settings: Settings, days: int = 7) -> CategoryTrend:
    """Per-day match counts per attack category, for a date-adjustable chart
    (as opposed to get_top_categories' single all-time ranking). Every day
    in the requested window is included even with zero matches, so the
    x-axis stays continuous instead of skipping quiet days - same reasoning
    as get_trend's hourly buckets.
    """
    entries = load_entries(settings)
    today = datetime.now(timezone.utc).date()
    bucket_dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    buckets = [d.isoformat() for d in bucket_dates]
    bucket_index = {d: i for i, d in enumerate(buckets)}

    counts: dict[str, list[int]] = {}
    for entry in entries:
        if not entry.timestamp:
            continue
        bucket = entry.timestamp.date().isoformat()
        idx = bucket_index.get(bucket)
        if idx is None:
            continue
        for match in entry.matches:
            for tag in match.tags:
                if ATTACK_TAG_RE.match(tag):
                    category = category_label(tag)
                    counts.setdefault(category, [0] * days)[idx] += 1

    series = [
        CategorySeries(category=category, counts=day_counts)
        for category, day_counts in sorted(counts.items(), key=lambda kv: -sum(kv[1]))
    ]
    return CategoryTrend(buckets=buckets, series=series)


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


def get_country_counts(settings: Settings, limit: int = 50) -> list[CountryCount]:
    """Request counts per country, for the dashboard's request globe.
    Private/reserved/unresolvable client IPs (geoip_service.lookup_country
    returning None) are skipped entirely - there's no country to plot them
    under."""
    entries = load_entries(settings)
    counts: Counter[str] = Counter()
    blocked_counts: Counter[str] = Counter()
    names: dict[str, str] = {}
    for entry in entries:
        if not entry.client_ip:
            continue
        resolved = geoip_service.lookup_country(entry.client_ip)
        if resolved is None:
            continue
        code, name = resolved
        counts[code] += 1
        names[code] = name
        if entry.blocked:
            blocked_counts[code] += 1

    results = []
    for code, count in counts.most_common(limit):
        centroid = COUNTRY_CENTROIDS.get(code)
        if centroid is None:
            continue
        lat, lng = centroid
        results.append(
            CountryCount(
                country_code=code,
                country_name=names[code],
                lat=lat,
                lng=lng,
                count=count,
                blocked_count=blocked_counts.get(code, 0),
            )
        )
    return results
