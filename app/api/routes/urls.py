import secrets, string
from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.schema.url import UrlCreate
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.url import Url
from datetime import datetime, timezone

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

@router.get("/{short_code}", status_code=status.HTTP_200_OK)
def redirect_url(short_code:str, db:Session = Depends(get_db)):
    statement = select(Url).where(Url.short_code == short_code)
    url = db.scalar(statement)
    if url == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="url not found")

    if url.isActive == False:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="url is inactive")

    if url.expires_at and url.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="url has expired")

    url.click_count+=1
    db.commit()
    db.refresh(url)

    return RedirectResponse(url.original_url, status_code=status.HTTP_302_FOUND)

    


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_url(payload:UrlCreate, db: Session = Depends(get_db)):

    characters = string.ascii_letters + string.digits

    short_code = payload.custom_code or "".join(secrets.choice(characters)for _ in range(7))

    existing = db.scalar(select(Url).where(Url.short_code == short_code))
    if existing:
        raise HTTPException(status_code= status.HTTP_409_CONFLICT, detail="Short code already exists")

    url = Url(
        original_url = str(payload.original_url),
        short_code = short_code,
        expires_at = payload.expires_at
    )

    db.add(url)
    db.commit()
    db.refresh(url)

    return {"short_code": url.short_code, "original_url":url.original_url}


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_url(short_code:str, db:Session = Depends(get_db)):
    existing = db.scalar(select(Url).where(Url.short_code == short_code));
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short code not found.")

    existing.isActive = False;
    db.commit()
