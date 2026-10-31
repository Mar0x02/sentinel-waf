from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# These values are interpolated directly into generated ModSecurity config
# text (render_service.render_engine_settings()) - reject quotes/newlines
# so nobody can break out of a directive and inject an arbitrary one.
_NO_INJECTION_RE = r'^[^"\n\r]*$'


class EngineSettingsOut(BaseModel):
    audit_engine: Literal["On", "Off", "RelevantOnly"]
    audit_log_relevant_status: str
    request_body_access: bool
    response_body_access: bool
    request_body_limit: int
    response_body_limit: int
    response_body_mime_type: str
    advanced_config: str
    updated_at: datetime | None

    class Config:
        from_attributes = True


class EngineSettingsUpdate(BaseModel):
    audit_engine: Literal["On", "Off", "RelevantOnly"] = "RelevantOnly"
    audit_log_relevant_status: str = Field(default="^(?:5|4(?!04))", pattern=_NO_INJECTION_RE, max_length=200)
    request_body_access: bool = True
    response_body_access: bool = True
    request_body_limit: int = Field(default=13107200, ge=0, le=1_073_741_824)
    response_body_limit: int = Field(default=1048576, ge=0, le=1_073_741_824)
    response_body_mime_type: str = Field(default="text/html text/plain", max_length=500)
    # Deliberately no charset/injection restriction - arbitrary ModSecurity
    # directives are the whole point, same trust model as a custom rule
    # file (see models.EngineSettings.advanced_config).
    advanced_config: str = Field(default="", max_length=20_000)

    @field_validator("response_body_mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        # Space-separated MIME types only - letters, digits, '/', '-', '.', '+'.
        import re

        if not re.fullmatch(r"[A-Za-z0-9/\-.+ ]*", v):
            raise ValueError("response_body_mime_type may only contain MIME type tokens separated by spaces")
        return v
