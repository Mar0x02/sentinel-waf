import json
import shutil

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import FileKind, LogSink, Rule, RuleFile, RuleSet, Site


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
    Each rule set gets its own directory specifically so two sets that both
    ship a same-named .data file (e.g. two CRS versions) never collide.
    """
    base = settings.rules_render_dir
    _clear_dir(base)

    rule_sets = db.query(RuleSet).filter(RuleSet.enabled.is_(True)).order_by(RuleSet.order_seq).all()
    for rule_set in rule_sets:
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


def render_sites(db: Session, settings: Settings) -> None:
    base = settings.sites_render_dir
    _clear_dir(base)

    for site in db.query(Site).filter(Site.enabled.is_(True)).all():
        conf = f"""server {{
    listen {site.listen_port};
    server_name {site.domain};

    location / {{
        client_max_body_size 0;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_pass {site.upstream_url};
    }}
}}
"""
        (base / f"site-{site.id}.conf").write_text(conf)


def render_log_sinks(db: Session, settings: Settings) -> None:
    sinks = db.query(LogSink).filter(LogSink.enabled.is_(True)).all()
    data = [{"name": s.name, "protocol": s.protocol.value, "host": s.host, "port": s.port} for s in sinks]
    settings.log_sink_config_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_sink_config_path.write_text(json.dumps(data, indent=2))


def render_all(db: Session, settings: Settings) -> None:
    render_rules(db, settings)
    render_sites(db, settings)
    render_log_sinks(db, settings)
