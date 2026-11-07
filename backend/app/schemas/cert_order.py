from pydantic import BaseModel


class CertOrderOut(BaseModel):
    status: str  # "pending_dns" | "issued" | "failed"
    dns_name: str
    dns_value: str
    error_message: str | None = None
