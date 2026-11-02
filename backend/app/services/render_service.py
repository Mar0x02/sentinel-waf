import json
import shutil

from sqlalchemy.orm import Session

from app.config import Settings
from app.default_engine_settings import DEFAULT_ADVANCED_CONFIG
from app.default_error_pages import DEFAULT_ERROR_PAGES
from app.models import DiscordWebhook, EngineSettings, ErrorPage, FileKind, LogSink, Rule, RuleFile, RuleSet, Site
from app.services.importer import BASE_TUNING_RULE_SET_SLUG


def _clear_dir(path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def render_rules(db: Session, settings: Settings) -> None:
    """Materializes the DB's rule state into the shared volume waf-engine
    reads from. Always does a full wipe + rewrite rather than an in-place
    diff - rule content is small and this changes rarely enough that
    correctness (no stale leftover files from a deleted/disabled set) is
    worth more than the extra I/O.

    Directory layout (see CLAUDE.md for the full rationale):
      <order_seq:04d>-<slug>/000-<setup file>.conf   (loads first in its set)
      <order_seq:04d>-<slug>/<original rule filename>.conf
      <order_seq:04d>-<slug>/<original .data filename>  (not Included, just
          present so @pmFromFile-style relative references resolve)
      zzz-overrides/000-overrides.conf                (always loads last)
      zzz-overrides/010-base-tuning.conf              (also always loads
          last - see below)
    Each rule set gets its own directory specifically so two sets that both
    ship a same-named .data file (e.g. two CRS versions) never collide.

    The "Base Tuning" rule set (BASE_TUNING_RULE_SET_SLUG) is deliberately
    excluded from the normal per-rule-set-directory loop and rendered into
    zzz-overrides/ instead. Its phase:2 content (id:100950/100960 in
    default_base_tuning.py) sums up and acts on tx.inbound_anomaly_score -
    it has to run after every *other* rule set's phase:2 contribution to
    that score, regardless of import order, so it needs the same
    guaranteed-last position SecRuleRemoveById already relies on. Its
    phase:1 content (the var scaffolding) doesn't actually need this - all
    phase:1 rules run before any phase:2 rule regardless of file order -
    but it's simpler to place the whole file there than to split it.
    """
    base = settings.rules_render_dir
    _clear_dir(base)

    rule_sets = db.query(RuleSet).filter(RuleSet.enabled.is_(True)).order_by(RuleSet.order_seq).all()
    base_tuning_file: RuleFile | None = None
    for rule_set in rule_sets:
        if rule_set.slug == BASE_TUNING_RULE_SET_SLUG:
            base_tuning_file = next((rf for rf in rule_set.files if rf.enabled), None)
            continue
        set_dir = base / f"{rule_set.order_seq:04d}-{rule_set.slug}"
        set_dir.mkdir(parents=True, exist_ok=True)
        for rule_file in rule_set.files:
            if not rule_file.enabled:
                continue
            out_name = f"000-{rule_file.filename}" if rule_file.file_kind == FileKind.setup else rule_file.filename
            (set_dir / out_name).write_text(rule_file.content)

    disabled_ids = (
        db.query(Rule.rule_id)
        .join(RuleFile, Rule.rule_file_id == RuleFile.id)
        .join(RuleSet, RuleFile.rule_set_id == RuleSet.id)
        .filter(
            Rule.enabled.is_(False),
            Rule.rule_id.isnot(None),
            RuleFile.enabled.is_(True),
            RuleSet.enabled.is_(True),
        )
        .distinct()
        .all()
    )
    overrides_dir = base / "zzz-overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Managed by the dashboard - do not edit directly, see the Rules page."]
    lines += [f"SecRuleRemoveById {rule_id}" for (rule_id,) in disabled_ids]
    (overrides_dir / "000-overrides.conf").write_text("\n".join(lines) + "\n")

    if base_tuning_file is not None:
        (overrides_dir / "010-base-tuning.conf").write_text(base_tuning_file.content)


_PROXY_LOCATION = """    location / {{
{limit_directives}        client_max_body_size 0;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_pass {upstream_url};
    }}"""


def _rate_limit_zone_names(site: Site) -> tuple[str, str]:
    return f"rl_req_{site.id}", f"rl_conn_{site.id}"


def _rate_limit_directives(site: Site) -> tuple[list[str], str]:
    """Returns (zone declaration lines for the http-level zones file,
    per-site "limit_req"/"limit_conn" lines to drop inside its location
    block). Both nginx mechanisms are independent toggles - see
    schemas/sites.py's _RateLimitFieldsMixin - and both are set to return
    429 so they land on the same "rate limited" error page CLAUDE.md notes
    was already reserved in waf-engine/error-pages.conf, waiting for
    exactly this.
    """
    req_zone, conn_zone = _rate_limit_zone_names(site)
    zone_lines: list[str] = []
    location_lines: list[str] = []

    if site.rate_limit_enabled:
        zone_lines.append(f"limit_req_zone $binary_remote_addr zone={req_zone}:10m rate={site.rate_limit_rps}r/s;")
        location_lines.append(f"        limit_req zone={req_zone} burst={site.rate_limit_burst} nodelay;\n")
    if site.conn_limit_enabled:
        zone_lines.append(f"limit_conn_zone $binary_remote_addr zone={conn_zone}:10m;")
        location_lines.append(f"        limit_conn {conn_zone} {site.conn_limit_per_ip};\n")

    return zone_lines, "".join(location_lines)


def render_sites(db: Session, settings: Settings) -> None:
    """Writes one nginx server block per enabled Site (two, if TLS is
    enabled: a redirect-only block on listen_port, plus the real
    ssl-terminating one on tls_listen_port - see CLAUDE.md's TLS section).
    Cert/key files live in a certs/ subdirectory of the same shared volume
    rather than a separate one - they're wiped and rewritten on every
    render pass same as the site-*.conf files, no extra volume needed.

    Per-IP rate/connection limit zones (limit_req_zone/limit_conn_zone)
    must be declared at the nginx http level before any server block
    references them by name. conf.d is already included inside http{} (see
    CLAUDE.md "Verified facts"), and dashboard-sites/*.conf is globbed
    alphabetically - so the zone declarations go in their own
    000-ratelimit-zones.conf, which sorts before every site-<id>.conf by
    construction (same "000-" / "zzz-" sort-order trick used for CRS setup
    files and SecRuleRemoveById overrides elsewhere in this project).
    """
    base = settings.sites_render_dir
    _clear_dir(base)
    certs_dir = base / "certs"
    all_zone_lines: list[str] = []

    for site in db.query(Site).filter(Site.enabled.is_(True)).all():
        zone_lines, limit_directives = _rate_limit_directives(site)
        all_zone_lines.extend(zone_lines)

        if site.tls_enabled and site.tls_cert and site.tls_key:
            certs_dir.mkdir(parents=True, exist_ok=True)
            cert_path = certs_dir / f"site-{site.id}.crt"
            key_path = certs_dir / f"site-{site.id}.key"
            cert_path.write_text(site.tls_cert)
            key_path.write_text(site.tls_key)
            key_path.chmod(0o600)

            https_target = (
                f"https://$host{':' + str(site.tls_listen_port) if site.tls_listen_port != 443 else ''}$request_uri"
            )
            conf = f"""server {{
    listen {site.listen_port};
    server_name {site.domain};

    include includes/sentinel-error-pages.conf;

    location / {{
        return 301 {https_target};
    }}
}}

server {{
    listen {site.tls_listen_port} ssl;
    server_name {site.domain};

    ssl_certificate /etc/nginx/conf.d/dashboard-sites/certs/site-{site.id}.crt;
    ssl_certificate_key /etc/nginx/conf.d/dashboard-sites/certs/site-{site.id}.key;

    include includes/sentinel-error-pages.conf;

{_PROXY_LOCATION.format(upstream_url=site.upstream_url, limit_directives=limit_directives)}
}}
"""
        else:
            conf = f"""server {{
    listen {site.listen_port};
    server_name {site.domain};

    include includes/sentinel-error-pages.conf;

{_PROXY_LOCATION.format(upstream_url=site.upstream_url, limit_directives=limit_directives)}
}}
"""
        (base / f"site-{site.id}.conf").write_text(conf)

    if all_zone_lines:
        zones_conf = "\n".join(
            [
                "# Managed by the dashboard - do not edit directly, see the Sites page.",
                "limit_req_status 429;",
                "limit_conn_status 429;",
                *all_zone_lines,
            ]
        )
        (base / "000-ratelimit-zones.conf").write_text(zones_conf + "\n")


def render_error_pages(db: Session, settings: Settings) -> None:
    base = settings.error_pages_render_dir
    base.mkdir(parents=True, exist_ok=True)
    customized = {row.status_code: row.html_content for row in db.query(ErrorPage).all()}
    for status_code, default_html in DEFAULT_ERROR_PAGES.items():
        html = customized.get(status_code, default_html)
        (base / f"{status_code}.html").write_text(html)


def get_or_create_engine_settings(db: Session) -> EngineSettings:
    """Shared by the API and the startup render pass. Must actually
    persist the row (not just construct it in memory) - SQLAlchemy only
    fills in a column's `default=` at INSERT time, so an unsaved
    `EngineSettings(id=1)` has every other field as plain Python `None`,
    not the model's defaults. Confirmed by a real bug: before this used
    add+commit+refresh here, the very first render (before anyone ever
    opened the Settings page) wrote `SecRequestBodyLimit None` etc.
    straight into the rendered ModSecurity config.
    """
    row = db.get(EngineSettings, 1)
    if row is None:
        row = EngineSettings(id=1, advanced_config=DEFAULT_ADVANCED_CONFIG)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def render_engine_settings(db: Session, settings: Settings) -> None:
    """Writes the single global ModSecurity engine directives file. Values
    are validated/sanitized at the API layer (schemas/engine_settings.py)
    before ever reaching here, since they're interpolated directly into
    ModSecurity config text.
    """
    base = settings.engine_settings_render_dir
    _clear_dir(base)
    row = get_or_create_engine_settings(db)

    def _onoff(flag: bool) -> str:
        return "On" if flag else "Off"

    lines = [
        "# Managed by the dashboard - do not edit directly, see the Settings page.",
        f"SecAuditEngine {row.audit_engine}",
        f'SecAuditLogRelevantStatus "{row.audit_log_relevant_status}"',
        f"SecRequestBodyAccess {_onoff(row.request_body_access)}",
        f"SecResponseBodyAccess {_onoff(row.response_body_access)}",
        f"SecRequestBodyLimit {row.request_body_limit}",
        f"SecResponseBodyLimit {row.response_body_limit}",
        f"SecResponseBodyMimeType {row.response_body_mime_type}",
    ]
    (base / "000-engine-settings.conf").write_text("\n".join(lines) + "\n")

    # Separate file, named to sort after 000-engine-settings.conf, so any
    # directive here can override a structured one above if the admin
    # wants that - and so a syntax mistake here can't accidentally break
    # the structured settings' own file.
    advanced_lines = [
        "# Managed by the dashboard - do not edit directly, see the Settings page.",
        "# Free-form directives from the Advanced section.",
        row.advanced_config,
    ]
    (base / "999-advanced.conf").write_text("\n".join(advanced_lines) + "\n")


def render_log_sinks(db: Session, settings: Settings) -> None:
    sinks = db.query(LogSink).filter(LogSink.enabled.is_(True)).all()
    data = [{"name": s.name, "protocol": s.protocol.value, "host": s.host, "port": s.port} for s in sinks]
    settings.log_sink_config_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_sink_config_path.write_text(json.dumps(data, indent=2))


def render_discord_webhooks(db: Session, settings: Settings) -> None:
    webhooks = db.query(DiscordWebhook).filter(DiscordWebhook.enabled.is_(True)).all()
    data = [{"name": w.name, "webhook_url": w.webhook_url} for w in webhooks]
    settings.discord_webhook_config_path.parent.mkdir(parents=True, exist_ok=True)
    settings.discord_webhook_config_path.write_text(json.dumps(data, indent=2))


def render_all(db: Session, settings: Settings) -> None:
    render_rules(db, settings)
    render_sites(db, settings)
    render_log_sinks(db, settings)
    render_error_pages(db, settings)
    render_engine_settings(db, settings)
    render_discord_webhooks(db, settings)
