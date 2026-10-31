from datetime import datetime

from pydantic import BaseModel


class ErrorPageOut(BaseModel):
    status_code: int
    title: str
    html_content: str
    is_customized: bool
    updated_at: datetime | None


class ErrorPageUpdate(BaseModel):
    html_content: str
