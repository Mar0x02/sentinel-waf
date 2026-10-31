from datetime import datetime

from pydantic import BaseModel, Field


class ErrorPageOut(BaseModel):
    status_code: int
    title: str
    html_content: str
    is_customized: bool
    updated_at: datetime | None


class ErrorPageUpdate(BaseModel):
    # Intentionally allows arbitrary HTML - this is served verbatim to
    # blocked visitors by design, same trust model as a custom rule file
    # (admin/operator authored, write-gated by role). The length cap is
    # just hygiene against an abusive/compromised account storing a huge
    # payload, not a content restriction.
    html_content: str = Field(max_length=100_000)
