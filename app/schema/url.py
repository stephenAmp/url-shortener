from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime, timezone

class UrlCreate(BaseModel):
    original_url: HttpUrl
    custom_code: str | None = None
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def convert_expires_at_to_utc(cls, value):
        if value is None:
            return None
        
        return value.astimezone(timezone.utc)

class ShortenedUrl(BaseModel):
    shortened_url: HttpUrl