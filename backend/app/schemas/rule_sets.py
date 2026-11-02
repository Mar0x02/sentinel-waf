import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import FileKind, SourceType


class RuleSetOut(BaseModel):
    id: int
    name: str
    slug: str
    source_type: SourceType
    source_url: str | None
    version: str | None
    order_seq: int
    enabled: bool
    created_at: datetime
    file_count: int
    rule_count: int
    # Only ever non-empty in the response of an import endpoint - rule IDs
    # of tunables whose value was automatically carried over from another
    # already-tuned setup file (same id + same variable names) onto this
    # newly imported one. See importer.py's _carry_over_crs_tuning. Always
    # [] on a plain GET/list, no point recomputing it after the fact.
    carried_over_tunables: list[str] = []

    class Config:
        from_attributes = True


class RuleFileOut(BaseModel):
    id: int
    rule_set_id: int
    filename: str
    file_kind: FileKind
    enabled: bool
    size_bytes: int
    rule_count: int
    created_at: datetime
    updated_at: datetime
    warnings: list["TxVarWarningOut"] = []

    class Config:
        from_attributes = True


class RuleFileContentOut(BaseModel):
    id: int
    filename: str
    content: str


class SetupFileStatusOut(BaseModel):
    """One other rule set's setup file (e.g. an imported CRS's
    crs-setup.conf), shown read-only from Base Tuning's own detail page -
    see RuleSetDetailPage's RelatedSetupFilesPanel. `in_use` mirrors
    render_service.render_rules()'s own skip conditions exactly (rule set
    disabled, or the file itself disabled) rather than re-deriving the
    logic differently here.
    """

    rule_set_id: int
    rule_set_name: str
    rule_set_slug: str
    rule_file_id: int
    filename: str
    size_bytes: int
    in_use: bool


class TunableFixOut(BaseModel):
    rule_set_id: int
    rule_set_name: str
    tunable_rule_id: str
    variables: dict[str, str]
    is_new: bool = False
    init_collection: str | None = None


class TxVarWarningOut(BaseModel):
    variable: str
    rule_id: str | None
    snippet: str
    fix: TunableFixOut | None = None
    kind: str = "undefined_var"


class RuleFileVersionOut(BaseModel):
    id: int
    created_at: datetime
    content: str
    size_bytes: int

    class Config:
        from_attributes = True


class LintRequest(BaseModel):
    content: str
    rule_file_id: int | None = None


class LintResult(BaseModel):
    warnings: list[TxVarWarningOut]


class RuleOut(BaseModel):
    id: int
    rule_file_id: int
    rule_id: str | None
    message: str | None
    raw_snippet: str
    enabled: bool
    order_index: int

    class Config:
        from_attributes = True


class ImportFromCatalogRequest(BaseModel):
    catalog_id: str


class ImportFromUrlRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str
    version: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("url must start with http:// or https://")
        return v


class CustomRuleFileCreate(BaseModel):
    filename: str = Field(pattern=r"^[A-Za-z0-9_\-]+\.conf$")
    content: str


class CustomRuleFileUpdate(BaseModel):
    content: str


class EnabledPatch(BaseModel):
    enabled: bool


class CrsTuningOut(BaseModel):
    blocking_paranoia_level: int
    detection_paranoia_level: int
    inbound_anomaly_score_threshold: int
    outbound_anomaly_score_threshold: int


class TunableGroupOut(BaseModel):
    rule_id: str
    description: str | None
    is_active: bool
    variables: dict[str, str]


class TunableGroupUpdate(BaseModel):
    is_active: bool
    variables: dict[str, str] = Field(max_length=20)

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: dict[str, str]) -> dict[str, str]:
        # Values are interpolated directly into generated ModSecurity
        # config text - reject anything that could break out of the
        # setvar:tx.X=<value> slot it's substituted into.
        for name, value in v.items():
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                raise ValueError(f"Invalid variable name: {name}")
            if re.search(r'["\n\r,]', value):
                raise ValueError(f"Value for {name} may not contain quotes, commas, or newlines")
        return v


class TunableGroupCreate(BaseModel):
    """For adding a brand-new tunable block (Base Tuning, via the lint
    warning's "add it" fix) rather than editing an existing one - see
    tunable_scanner.add_tunable(). Same injection guard as
    TunableGroupUpdate since these values land in the same setvar:tx.X=
    slot either way."""

    rule_id: str = Field(pattern=r"^[0-9]+$", max_length=10)
    phase: int = Field(default=1, ge=1, le=5)
    variables: dict[str, str] = Field(max_length=20, min_length=1)

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, v: dict[str, str]) -> dict[str, str]:
        for name, value in v.items():
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                raise ValueError(f"Invalid variable name: {name}")
            if re.search(r'["\n\r,]', value):
                raise ValueError(f"Value for {name} may not contain quotes, commas, or newlines")
        return v


class InitCollectionRequest(BaseModel):
    """For the "uninitialized_collection" lint fix - appends
    initcol:<collection>=%{REMOTE_ADDR} as a new SecAction. collection is
    restricted to ModSecurity's own three persistent-collection names
    (ip/session/user) - anything else can't be a real initcol target."""

    rule_id: str = Field(pattern=r"^[0-9]+$", max_length=10)
    collection: str = Field(pattern=r"^(ip|session|user)$")
    phase: int = Field(default=1, ge=1, le=5)


class CrsTuningUpdate(BaseModel):
    blocking_paranoia_level: int = Field(ge=1, le=4)
    detection_paranoia_level: int = Field(ge=1, le=4)
    inbound_anomaly_score_threshold: int = Field(ge=0, le=1000)
    outbound_anomaly_score_threshold: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def check_detection_not_below_blocking(self) -> "CrsTuningUpdate":
        # CRS's own documented constraint: detection_paranoia_level must
        # not be lower than blocking_paranoia_level.
        if self.detection_paranoia_level < self.blocking_paranoia_level:
            raise ValueError("detection_paranoia_level must not be lower than blocking_paranoia_level")
        return self
