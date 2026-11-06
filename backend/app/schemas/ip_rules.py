import ipaddress
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import IpRuleAction


class IpRuleOut(BaseModel):
    id: int
    ip: str
    action: IpRuleAction
    note: str | None
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class IpRuleCreate(BaseModel):
    ip: str = Field(min_length=1, max_length=64)
    action: IpRuleAction
    note: str | None = Field(default=None, max_length=200)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        # Accepts a single IP or a CIDR range - @ipMatch (used by
        # render_service.render_ip_rules) natively supports both. This also
        # closes off injection: a valid network has no quote/newline chars,
        # so it's always safe to interpolate directly into the rendered
        # SecRule text.
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as exc:
            raise ValueError("must be a valid IP address or CIDR range") from exc
        return v


class EnabledPatch(BaseModel):
    enabled: bool
