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

    class Config:
        from_attributes = True


class RuleFileContentOut(BaseModel):
    id: int
    filename: str
    content: str


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
