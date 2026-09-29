import uuid
from typing import Annotated
from fastapi import APIRouter, status, Depends, Request, Query
from app.schema.url import UrlCreate, ClickResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.url import UrlService
from datetime import datetime

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

# Shouldnt fetch when page is empty the number of pages that are available with data should show
@router.get("/{short_code}", status_code=status.HTTP_200_OK)
def redirect_url(short_code:str, request:Request, db:Session = Depends(get_db)):
    return UrlService(db).get_redirect_url(short_code, request)


# Create url
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_url(payload:UrlCreate, db: Session = Depends(get_db)):
    return UrlService(db).create_url(payload)

# Deactivate url
@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_url(short_code:str, db:Session = Depends(get_db)):
    return UrlService(db).deactivate_url(short_code)

# Get all URLs
# pagination params ?page=1&limit=10
@router.get("/", status_code=status.HTTP_200_OK)
def get_all_urls(
    page: Annotated[int, Query(ge=1, description="Must be greater than 1"),] = 1, 
    limit: Annotated[int, Query(ge=1, le=100, description="Must be between 1 and 100")]  = 10, 
    q: str | None = None,
    is_active: bool | None = None,
    created_from: datetime | None = None,
    created_before: datetime | None = None,
    db:Session = Depends(get_db)
    ):
    return UrlService(db).get_urls(page, limit, q, is_active, created_from, created_before)

# Get Url details
@router.get("/{uuid}/analytics", response_model=list[ClickResponse], status_code=status.HTTP_200_OK)
def get_url_details(uuid:uuid.UUID, db:Session = Depends(get_db)):
    return UrlService(db).get_url_details(uuid)

# Delete url 
@router.delete("/{uuid}/remove", status_code=status.HTTP_204_NO_CONTENT)
def delete_url(uuid:uuid.UUID, db:Session = Depends(get_db)):
    return UrlService(db).delete_url(uuid)

# activate url
@router.patch("/{uuid}/activate", status_code=status.HTTP_200_OK)
def activate_url(uuid:uuid.UUID, db:Session = Depends(get_db)):
    return UrlService(db).activate_url(uuid)