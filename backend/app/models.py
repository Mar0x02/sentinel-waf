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
