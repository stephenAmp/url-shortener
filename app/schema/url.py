from pydantic import BaseModel, HttpUrl

class UrlCreate(BaseModel):
    original_url: HttpUrl

class ShortenedUrl(BaseModel):
    shortened_url: HttpUrl