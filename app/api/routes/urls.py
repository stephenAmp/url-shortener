import secrets, string
from fastapi import APIRouter, status, Depends, HTTPException
from app.schema.url import UrlCreate
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.url import Url
from app.services.url import UrlService

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

@router.get("/{short_code}", status_code=status.HTTP_200_OK)
def redirect_url(short_code:str, db:Session = Depends(get_db)):
    return UrlService(db).get_redirect_url(short_code)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_url(payload:UrlCreate, db: Session = Depends(get_db)):
    return UrlService(db).create_url(payload)


@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_url(short_code:str, db:Session = Depends(get_db)):
    return UrlService(db).deactivate_url(short_code)