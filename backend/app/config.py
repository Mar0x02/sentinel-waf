from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://waf:waf@postgres:5432/waf"

    # Shared volume (also mounted into the waf-engine container) that this
    # backend renders ModSecurity rule config into. Structure is rendered by
    # app/services/render_service.py - see CLAUDE.md for the exact layout
    # and why it's shaped this way (Include glob ordering, data-file name
    # collisions across rule sets, etc).
    rules_render_dir: Path = Path("/render/modsecurity-rules")

    # Shared volume (also mounted into the waf-engine container) where one
    # nginx server block per enabled Site is rendered.
    sites_render_dir: Path = Path("/render/nginx-sites")

    # Shared volume (also mounted into the log-forwarder container) holding
    # the rendered log sink configuration (see app/services/render_service.py).
    log_sink_config_path: Path = Path("/render/log-sinks/log-sinks.json")

    # Shared volume (also mounted into the log-forwarder container) holding
    # the rendered Discord webhook configuration.
    discord_webhook_config_path: Path = Path("/render/discord/webhooks.json")

    # Shared volume (also mounted into the waf-engine container) holding
    # rendered <status_code>.html files - see app/default_error_pages.py
    # and waf-engine/error-pages.conf.
    error_pages_render_dir: Path = Path("/render/error-pages")

    # Shared volume (also mounted into the waf-engine container) holding
    # the rendered global ModSecurity engine directives (SecAuditEngine,
    # body inspection limits, etc.) - see models.EngineSettings.
    engine_settings_render_dir: Path = Path("/render/engine-settings")

    # Shared volume (also mounted into the waf-engine container) holding
    # the rendered IP allow/blocklist - see models.IpRule and
    # app/services/render_service.render_ip_rules().
    ip_rules_render_dir: Path = Path("/render/ip-rules")

    # Directory containing the *live* (currently-being-written) ModSecurity
    # audit log file(s) - this is what the Logs page / Dashboard read.
    # waf-engine's docker-entrypoint.d/03-audit-log-rotate.sh keeps exactly
    # one small file here (the rest of the shared volume is the separate
    # audit_log_archive_dir below), so this directory never grows unbounded.
    audit_log_dir: Path = Path("/data/logs/live")

    # Directory of day-folders (YYYY-MM-DD) holding gzip-compressed, no
    # longer live-browsable audit log chunks - rendered by the same rotate
    # script, read by app/services/log_archive_service.py for the Log
    # Archive page. Archiving (not deleting) is the point: nothing here
    # gets pruned automatically.
    audit_log_archive_dir: Path = Path("/data/logs/archive")

    # Which audit log parser/adapter to use. See app/adapters/.
    # "modsec_v3_json" = ModSecurity v3 (libmodsecurity) JSON audit log,
    # the default format produced by the nginx connector / coreruleset
    # docker images. Add more adapters here as other WAF backends are
    # supported (e.g. Apache + mod_security2 native format).
    audit_log_format: str = "modsec_v3_json"

    # ACME (Let's Encrypt) directory URL for the dns-01 automated cert flow
    # - see app/services/acme_service.py. Override to the staging directory
    # (https://acme-staging-v02.api.letsencrypt.org/directory) while testing,
    # to avoid Let's Encrypt's production rate limits.
    acme_directory_url: str = "https://acme-v02.api.letsencrypt.org/directory"
    # Optional contact email for the ACME account (expiry reminders from the
    # CA). Not required - Let's Encrypt accepts account registration with
    # no contact at all.
    acme_contact_email: str | None = None

    class Config:
        env_prefix = "WAF_"
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
