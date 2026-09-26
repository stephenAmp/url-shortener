import string, secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from app.db.models.url import Url
from datetime import datetime, timezone
from sqlalchemy import select
from app.schema.url import UrlCreate

class UrlService:
    def __init__(self, db:Session):
        self.db = db

    def  get_redirect_url(self, short_code:str) -> str:
        existing = select(Url).where(Url.short_code == short_code)
        url = self.db.scalar(existing)

        if url == None:
            raise HTTPException(status_code= status.HTTP_404_NOT_FOUND, detail = "url resource cannot be found.")

        if url.isActive == False:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="url is inactive")

        if url.expires_at and url.expires_at  <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="url has expired")

        url.click_count+=1
        self.db.commit()
        self.db.refresh(url)

        return RedirectResponse(url, status_code=status.HTTP_302_FOUND)

    def create_url(self, payload:UrlCreate) -> dict[str, str]:
        characters = string.ascii_letters + string.digits
        short_code = payload.custom_code or "" .join(secrets.choice(characters)for _ in range(7))
        statement = select(Url).where(Url.short_code == short_code)
        existing = self.db.scalar(statement)
        
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="custom code already exists")

        url = Url(
            original_url = str(payload.original_url), 
            short_code=short_code, 
            expires_at=payload.expires_at
            )
        self.db.add(url)
        self.db.commit()
        self.db.refresh(url)

        return {"short_code":url.short_code, "original_url":url.original_url}


    def deactivate_url(self, short_code:str) -> None:
        statement = select(Url).where(Url.short_code == short_code)
        url = self.db.scalar(statement)

        if url is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="url not found.")

        url.isActive = False

        self.db.commit()


