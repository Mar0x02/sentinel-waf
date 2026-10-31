from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DiscordWebhookOut(BaseModel):
    id: int
    name: str
    webhook_url: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DiscordWebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    webhook_url: str

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        # Sanity check, not a security boundary - this is an admin-only,
        # self-configured outbound destination. Mainly catches typos/wrong
        # URLs pasted in by mistake.
        if not v.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
            raise ValueError("Must be a Discord webhook URL (https://discord.com/api/webhooks/...)")
        return v


class DiscordWebhookUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    webhook_url: str

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not v.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
            raise ValueError("Must be a Discord webhook URL (https://discord.com/api/webhooks/...)")
        return v


class EnabledPatch(BaseModel):
    enabled: bool
