import uuid
import string, secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request
from fastapi.responses import RedirectResponse
from app.db.models.url import Url, Click
from datetime import datetime, timezone
from sqlalchemy import select
from app.schema.url import UrlCreate

class UrlService:
    def __init__(self, db:Session):
        self.db = db

    def  get_redirect_url(self, short_code:str, request:Request) -> str:
        existing = select(Url).where(Url.short_code == short_code)
        url = self.db.scalar(existing)

        if url == None:
            raise HTTPException(status_code= status.HTTP_404_NOT_FOUND, detail = "url resource cannot be found.")

        if url.isActive == False:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="url is inactive")

        if url.expires_at and url.expires_at  <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="url has expired")

        referrer = request.headers.get("referrer")
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        click_detail = Click(
            referrer = referrer,
            ip_address = ip_address,
            user_agent = user_agent
        )
        self. db.add(click_detail)

        url.click_count+=1

        self.db.commit()
        self.db.refresh(url)
        self.db.refresh(click_detail)

        return RedirectResponse(url.original_url, status_code=status.HTTP_302_FOUND)


    def get_urls(self, page: int = 1, limit:int = 10) -> list[Url]:
        offset = (page - 1) * limit
        statement = select(Url).offset(offset).limit(limit)
        urls = self.db.scalars(statement).all()
        return urls


    def get_url_details(self, uuid:uuid.UUID) -> list[Click]:
        statement = select(Click).where(Click.url_uuid == uuid)
        clicks = self.db.scalars(statement).all()
        return clicks



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

        if not url.isActive:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="url is already inactive")

        url.isActive = False

        self.db.commit()


    def delete_url(self, uuid:uuid.UUID) -> None:
        statement = select(Url).where(Url.uuid == uuid)
        url = self.db.scalar(statement)

        if url is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="url not found")

        self.db.delete(url)
        self.db.commit()



    def activate_url(self, short_code) -> Url:
        statement = select(Url).where(Url.short_code == short_code)
        url = self.db.scalar(statement)

        if url is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "url not found.")

        if url.isActive:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="url is already active.")

        url.isActive = True

        self.db.commit()
        self.db.refresh(url)
        return url