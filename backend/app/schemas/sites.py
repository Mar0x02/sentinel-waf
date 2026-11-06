import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.tls_service import CertValidationError, validate_cert_key_pair

_DOMAIN_RE = r"^(\*\.)?[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
# Scheme + host[:port] only - no path/query, so this can never inject
# anything beyond the proxy_pass target when rendered into nginx config.
_UPSTREAM_RE = r"^https?://[a-zA-Z0-9.\-]+(:[0-9]{1,5})?$"


class _AddressFieldsMixin(BaseModel):
    # Plain str + field_validator rather than Field(pattern=...) so the API
    # (and therefore the frontend toast, which just shows this message
    # verbatim - see api/client.ts's describeErrorDetail) says what's
    # actually wrong instead of Pydantic's default "String should match
    # pattern '^https?://...'" dump of the raw regex.
    domain: str
    upstream_url: str

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, v: str) -> str:
        if not re.fullmatch(_DOMAIN_RE, v):
            raise ValueError("Domain must be a plain hostname, e.g. example.com or *.example.com - no scheme, path, or port")
        return v

    @field_validator("upstream_url")
    @classmethod
    def _validate_upstream_url(cls, v: str) -> str:
        if not re.fullmatch(_UPSTREAM_RE, v):
            raise ValueError(
                "Upstream URL must include the scheme, e.g. http://10.10.10.10 or https://backend:8080 - no path"
            )
        return v


class SiteOut(BaseModel):
    id: int
    name: str
    domain: str
    upstream_url: str
    listen_port: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    # TLS: tls_cert/tls_key are intentionally never exposed here, even to an
    # admin re-fetching their own site - write-only, same as a password
    # field. has_cert + cert_expires_at are the only client-visible signal
    # that a cert is stored, derived in api/sites.py at response time.
    tls_enabled: bool
    tls_listen_port: int
    has_cert: bool = False
    cert_expires_at: datetime | None = None
    rate_limit_enabled: bool
    rate_limit_rps: int
    rate_limit_burst: int
    conn_limit_enabled: bool
    conn_limit_per_ip: int
    bot_challenge_enabled: bool
    honeypot_checkbox_enabled: bool
    honeypot_path_enabled: bool
    block_bad_user_agents: bool

    class Config:
        from_attributes = True


class _TlsFieldsMixin(BaseModel):
    tls_enabled: bool = False
    tls_listen_port: int = Field(default=8443, ge=1, le=65535)
    # None/omitted means "leave whatever cert is already stored alone" on an
    # update (SiteUpdate) - see api/sites.py. On create there's nothing to
    # keep, so the endpoint requires both when tls_enabled is True.
    tls_cert: str | None = None
    tls_key: str | None = None

    @model_validator(mode="after")
    def _validate_tls_pair(self):
        cert, key = self.tls_cert, self.tls_key
        if (cert is None) != (key is None):
            raise ValueError("tls_cert and tls_key must be provided together")
        if cert is not None and key is not None:
            try:
                validate_cert_key_pair(cert, key)
            except CertValidationError as exc:
                raise ValueError(str(exc)) from exc
        return self


class _RateLimitFieldsMixin(BaseModel):
    # Per-IP request rate (nginx limit_req) - rps is a steady-state cap,
    # burst is how many requests above that rate are queued (not dropped)
    # before limit_req_status 429 kicks in. See render_service.py.
    rate_limit_enabled: bool = False
    rate_limit_rps: int = Field(default=20, ge=1, le=100_000)
    rate_limit_burst: int = Field(default=40, ge=0, le=100_000)
    # Per-IP concurrent connection cap (nginx limit_conn), independent of
    # the above - guards against connection-holding abuse (e.g. slowloris
    # style) that a request-rate limit alone doesn't catch.
    conn_limit_enabled: bool = False
    conn_limit_per_ip: int = Field(default=50, ge=1, le=100_000)


class _AntiBotFieldsMixin(BaseModel):
    # Anti-Bot menu (dedicated page) - see render_service.py's
    # _proxy_location() and waf-engine/njs/bot_challenge.js.
    bot_challenge_enabled: bool = False
    honeypot_checkbox_enabled: bool = False
    honeypot_path_enabled: bool = False
    block_bad_user_agents: bool = False

    @model_validator(mode="after")
    def _honeypot_checkbox_needs_challenge(self):
        # The decoy checkbox is a modifier of the challenge page - there's
        # no page to put it on if the JS challenge itself is off.
        if self.honeypot_checkbox_enabled and not self.bot_challenge_enabled:
            raise ValueError("honeypot_checkbox_enabled requires bot_challenge_enabled")
        return self


class AntiBotUpdate(_AntiBotFieldsMixin):
    pass


class SiteCreate(_TlsFieldsMixin, _RateLimitFieldsMixin, _AntiBotFieldsMixin, _AddressFieldsMixin):
    name: str = Field(min_length=1, max_length=100)
    listen_port: int = Field(default=8080, ge=1, le=65535)

    @model_validator(mode="after")
    def _require_cert_if_enabled(self):
        if self.tls_enabled and self.tls_cert is None:
            raise ValueError("tls_cert and tls_key are required to enable HTTPS")
        return self


class SiteUpdate(_TlsFieldsMixin, _RateLimitFieldsMixin, _AntiBotFieldsMixin, _AddressFieldsMixin):
    name: str = Field(min_length=1, max_length=100)
    listen_port: int = Field(ge=1, le=65535)


class EnabledPatch(BaseModel):
    enabled: bool
