import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base


class SourceType(str, enum.Enum):
    catalog = "catalog"
    url = "url"
    custom = "custom"


class FileKind(str, enum.Enum):
    # "setup" files (e.g. crs-setup.conf) must load before "rule" files in
    # the same rule set - see render_service for how that's enforced.
    setup = "setup"
    rule = "rule"
    # Data files referenced by operators like @pmFromFile. Never toggled
    # individually, never matched by the rules Include glob (not *.conf).
    asset = "asset"


class Protocol(str, enum.Enum):
    udp = "udp"
    tcp = "tcp"


class RuleSet(Base):
    __tablename__ = "rule_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    # Controls render directory ordering (zero-padded prefix) - see
    # render_service. Assigned once at creation, never reused.
    order_seq: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    files: Mapped[list["RuleFile"]] = relationship(
        back_populates="rule_set", cascade="all, delete-orphan", order_by="RuleFile.filename"
    )


class RuleFile(Base):
    __tablename__ = "rule_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_set_id: Mapped[int] = mapped_column(ForeignKey("rule_sets.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_kind: Mapped[FileKind] = mapped_column(Enum(FileKind), default=FileKind.rule, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rule_set: Mapped[RuleSet] = relationship(back_populates="files")
    rules: Mapped[list["Rule"]] = relationship(
        back_populates="rule_file", cascade="all, delete-orphan", order_by="Rule.order_index"
    )


class Rule(Base):
    """Best-effort index over the individual SecRule/SecAction blocks found
    inside a RuleFile's content - used for listing/search/toggle in the UI.
    Rendering never reconstructs a file from these rows; it always writes
    RuleFile.content verbatim and layers SecRuleRemoveById on top for any
    rule here with enabled=False. See app/services/rule_parser.py.
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_file_id: Mapped[int] = mapped_column(ForeignKey("rule_files.id", ondelete="CASCADE"))
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rule_file: Mapped[RuleFile] = relationship(back_populates="rules")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    upstream_url: Mapped[str] = mapped_column(String, nullable=False)
    listen_port: Mapped[int] = mapped_column(Integer, default=8080, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LogSink(Base):
    __tablename__ = "log_sinks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    protocol: Mapped[Protocol] = mapped_column(Enum(Protocol), default=Protocol.udp, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ErrorPage(Base):
    """A customized error page for one status code. A missing row means
    "use the built-in default" - see app/default_error_pages.py. Only the
    fixed set of status codes baked into waf-engine/error-pages.conf are
    ever meaningful here (see CLAUDE.md).
    """

    __tablename__ = "error_pages"

    status_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Role(str, enum.Enum):
    # admin: everything, including managing other users.
    # operator: day-to-day WAF ops (rules/sites/error pages) but not user
    #   management or log-sink settings.
    # viewer: read-only everywhere (dashboard/logs/stats/rules/sites), no
    #   write endpoint of any kind - enforced per-endpoint, see CLAUDE.md.
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class User(Base):
    """A dashboard login account. See CLAUDE.md for the role model and how
    it's enforced (per-endpoint dependencies, not router-wide, since most
    routers mix read and write endpoints that need different checks).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.admin, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSecret(Base):
    """Generic key/value store for server-generated secrets (currently just
    the JWT signing key) that need to survive container restarts without
    requiring the user to configure anything. See app/auth.py.
    """

    __tablename__ = "app_secrets"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class EngineSettings(Base):
    """Global ModSecurity engine directives (SecAuditEngine, body
    inspection limits, etc.) - applies to every site, not per rule set.
    Singleton row (always id=1), get-or-create like AppSecret. Rendered
    into its own dashboard-controlled file that loads right after
    modsecurity.conf and overrides whatever the waf-engine image's env-var
    defaults set - see render_service.render_engine_settings() and
    CLAUDE.md.
    """

    __tablename__ = "engine_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_engine: Mapped[str] = mapped_column(String, default="RelevantOnly", nullable=False)
    audit_log_relevant_status: Mapped[str] = mapped_column(String, default="^(?:5|4(?!04))", nullable=False)
    request_body_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    response_body_access: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    request_body_limit: Mapped[int] = mapped_column(Integer, default=13107200, nullable=False)
    response_body_limit: Mapped[int] = mapped_column(Integer, default=1048576, nullable=False)
    response_body_mime_type: Mapped[str] = mapped_column(String, default="text/html text/plain", nullable=False)
    # Free-form ModSecurity directives for anything the structured fields
    # above don't cover (SecPcreMatchLimit, SecCollectionTimeout, etc).
    # Rendered verbatim, same trust model as a custom rule file's raw
    # content - no charset restriction, since arbitrary directives are the
    # point. Protected the same way any rendered config is: waf-engine's
    # watcher runs `nginx -t` before reloading and keeps the last-good
    # config running if this is invalid - see CLAUDE.md.
    advanced_config: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscordWebhook(Base):
    """A Discord channel to notify on every blocked request. Deliberately
    separate from LogSink (syslog) rather than a shared "sink with a type"
    table - different payload shape (Discord embeds vs syslog lines),
    different delivery mechanics (rate-limited HTTP POST vs a socket
    write), and admin-only for the same reason log sinks are: it's an
    external destination for WAF activity data, not day-to-day rule/site
    ops. See log-forwarder/forwarder.py for the actual delivery + batching.
    """

    __tablename__ = "discord_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    webhook_url: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
