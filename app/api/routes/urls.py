import uuid
from fastapi import APIRouter, status, Depends, Request
from app.schema.url import UrlCreate, ClickResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.url import UrlService

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

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
def get_all_urls(page: int = 1, limit: int = 10, db:Session = Depends(get_db)):
    return UrlService(db).get_urls(page, limit)

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