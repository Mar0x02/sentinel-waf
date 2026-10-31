from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Protocol

_HOST_RE = r"^[a-zA-Z0-9.\-]+$"


class LogSinkOut(BaseModel):
    id: int
    name: str
    protocol: Protocol
    host: str
    port: int
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LogSinkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    protocol: Protocol = Protocol.udp
    host: str = Field(pattern=_HOST_RE)
    port: int = Field(ge=1, le=65535)


class LogSinkUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    protocol: Protocol
    host: str = Field(pattern=_HOST_RE)
    port: int = Field(ge=1, le=65535)


class EnabledPatch(BaseModel):
    enabled: bool
