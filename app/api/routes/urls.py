import secrets
from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.schema.url import UrlCreate
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.url import Url

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

@router.get("/{short_code}", status_code=status.HTTP_200_OK)
def redirect_url(short_code:str, db:Session = Depends(get_db)):
    statement = select(Url).where(Url.short_code == short_code)
    url = db.scalar(statement)
    if url == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short url not found")

    url.click_count+=1
    db.commit()
    db.refresh(url)

    return {
        "url" : url.original_url,
        "status_code" : status.HTTP_302_FOUND,
        "click_count": url.click_count
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_url(payload:UrlCreate, db: Session = Depends(get_db)):

    short_code = secrets.token_urlsafe()
    url = Url(
        original_url = str(payload.original_url),
        short_code = short_code,
    )

    db.add(url)
    db.commit()
    db.refresh(url)

    return url