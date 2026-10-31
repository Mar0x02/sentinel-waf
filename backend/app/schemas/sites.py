from datetime import datetime

from pydantic import BaseModel, Field

_DOMAIN_RE = r"^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
# Scheme + host[:port] only - no path/query, so this can never inject
# anything beyond the proxy_pass target when rendered into nginx config.
_UPSTREAM_RE = r"^https?://[a-zA-Z0-9.\-]+(:[0-9]{1,5})?$"


class SiteOut(BaseModel):
    id: int
    name: str
    domain: str
    upstream_url: str
    listen_port: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    domain: str = Field(pattern=_DOMAIN_RE)
    upstream_url: str = Field(pattern=_UPSTREAM_RE)
    listen_port: int = Field(default=8080, ge=1, le=65535)


class SiteUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    domain: str = Field(pattern=_DOMAIN_RE)
    upstream_url: str = Field(pattern=_UPSTREAM_RE)
    listen_port: int = Field(ge=1, le=65535)


class EnabledPatch(BaseModel):
    enabled: bool
