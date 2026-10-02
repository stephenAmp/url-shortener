import uuid
import time
from typing import Annotated
from app.core.redis import redis_client
from fastapi import APIRouter, status, Depends, Request, Query, HTTPException
from app.schema.url import UrlCreate, ClickResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.url import UrlService
from datetime import datetime
from redis.exceptions import RedisError

router = APIRouter(
    prefix="/urls",
    tags=["URLs"]
)

# Rate limiting
def rate_limit(action: str, limit: int):
    def check_rate(request: Request) -> None:
        #TODO: At deployment, verify this is the real client IP behind the trusted proxy.
        ip = request.client.host if request.client else "unknown"
        now = int(time.time())

        key = f"rate:{action}:{ip}:{now // 60}"

        try:
            with redis_client.pipeline() as pipe:
                pipe.incr(key)
                pipe.expire(key, 120)
                count, _ = pipe.execute()
        except RedisError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable"
            )

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(60 - now % 60)}
            )

    return check_rate

  

# Shouldnt fetch when page is empty the number of pages that are available with data should show
@router.get("/{short_code}", status_code=status.HTTP_200_OK, dependencies=[Depends(rate_limit("urls:redirect",100))])
def redirect_url(short_code:str, request:Request, db:Session = Depends(get_db)):
    return UrlService(db).get_redirect_url(short_code, request)


# Create url
@router.post(
        "/", 
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(rate_limit("urls:create", 10))]
        )
def create_url(payload:UrlCreate, db: Session = Depends(get_db)):
    return UrlService(db).create_url(payload)

# Deactivate url
@router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_url(short_code:str, db:Session = Depends(get_db)):
    return UrlService(db).deactivate_url(short_code)

# Get all URLs
# pagination params ?page=1&limit=10
@router.get(
        "/", 
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(rate_limit("urls:list", 20))]
        )
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
@router.patch("/{short_code}/activate", status_code=status.HTTP_200_OK)
def activate_url(short_code:str, db:Session = Depends(get_db)):
    return UrlService(db).activate_url(short_code)
