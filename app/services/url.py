import uuid, json
import string, secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Request
from fastapi.responses import RedirectResponse
from app.db.models.url import Url, Click
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from app.schema.url import UrlCreate
from sqlalchemy import or_
from app.core.redis import redis_client
from redis.exceptions import RedisError

class UrlService:
    def __init__(self, db:Session):
        self.db = db

    def  get_redirect_url(self, short_code:str, request:Request) -> str:
        url_id = None
        destination = None
        cached_data = None

        try:
            raw = redis_client.get(f"url:{short_code}")
            if raw:
                value = json.loads(raw)
                if (
                        isinstance(value, dict) 
                        and isinstance(value.get("uuid"), str) 
                        and isinstance(value.get("original_url"), str)
                    ):
                    cached_data = value
                    url_id = uuid.UUID(cached_data["uuid"])
                    destination = cached_data['original_url']

        except (ValueError, RedisError, TypeError) as e:
                print("AN ERROR OCCURED LOOKING UP CACHE:", e)

        if not url_id or not destination:

            existing = select(Url).where(Url.short_code == short_code)
            url = self.db.scalar(existing)

            if url == None:
                raise HTTPException(status_code= status.HTTP_404_NOT_FOUND, detail = "url resource cannot be found.")

            if url.isActive == False:
                raise HTTPException(status_code=status.HTTP_410_GONE, detail="url is inactive")

            if url.expires_at and url.expires_at  <= datetime.now(timezone.utc):
                raise HTTPException(status_code=status.HTTP_410_GONE, detail="url has expired")

            url_id = url.uuid
            destination = url.original_url

            ttl = 60;
            if url.expires_at:
                ttl = min(ttl, int((url.expires_at - datetime.now(timezone.utc)).total_seconds()))

            if ttl > 0:
                try:
                    redis_client.set(
                        f"url:{short_code}",
                        json.dumps({"uuid":str(url.uuid), "original_url":url.original_url}), 
                        ex = ttl
                    )
                except RedisError:
                    pass

        referrer = request.headers.get("referrer")
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        click_detail = Click(
            url_uuid = url_id,
            referrer = referrer,
            ip_address = ip_address,
            user_agent = user_agent
        )

        result = self.db.execute(
            update(Url)
            .where(
                Url.uuid == url_id,
                Url.short_code == short_code,
                Url.isActive.is_(True),
                or_(
                Url.expires_at.is_(None),
                Url.expires_at > datetime.now(timezone.utc)
                ),
            ).values(click_count=Url.click_count + 1)
        )

        if result.rowcount != 1:
            self.db.rollback()
            try:
                redis_client.delete(f"url:{short_code}")
            except RedisError as e:
                print("REDIS ERROR:",e)

            statement = select(Url).where(Url.short_code == short_code)
            current = self.db.scalar(statement)
            if current is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "url not found")
            if not current.isActive or (
                current.expires_at and current.expires_at <= datetime.now(timezone.utc)
            ):
                raise HTTPException(status_code = status.HTTP_410_GONE, detail = "Url is expired or inactive")

            raise HTTPException(status_code = status.HTTP_409_CONFLICT, detail="url changed. Retry")

        self.db.add(click_detail)
        self.db.commit()

        return RedirectResponse(destination, status_code=status.HTTP_302_FOUND)


    def get_urls(
            self, 
            page: int = 1, 
            limit:int = 10, 
            q:str | None = None,
            is_active: bool | None = None,
            created_from: datetime | None = None,
            created_before: datetime | None = None,
        ) -> dict:

        filters = []
        if q:
            filters.append(or_(
                    Url.short_code.ilike(f"%{q}%"),
                    Url.original_url.ilike(f"%{q}%")
                )
            )

        if is_active is not None:
            filters.append(Url.isActive == is_active)
        if created_from is not None:
            filters.append(Url.created_at >= created_from)
        if created_before is not None:
            filters.append(Url.created_at < created_before)


        count_stm = select(func.count()).select_from(Url).where(*filters)
        total = self.db.scalar(count_stm) or 0
        
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        page = min(page, total_pages) if total > 0 else 1
        offset = (page - 1) * limit

        statement = (
            select(Url)
            .where(*filters)
            .order_by(Url.created_at.desc(),Url.uuid.desc())
            .offset(offset)
            .limit(limit)
            )
        urls = self.db.scalars(statement).all()
        
        return {
            "data": urls,
            "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        }
    }


    def get_url_details(self, uuid:uuid.UUID) -> list[Click]:
        statement = select(Click).where(Click.url_uuid == uuid)
        clicks = self.db.scalars(statement).all()

        print("CLICK DETAILS:", clicks)
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
        try:
            redis_client.delete(f"url:{url.short_code}")
        except RedisError:
            print("Failed to remove cached entry in redis")


    def delete_url(self, uuid:uuid.UUID) -> None:
        statement = select(Url).where(Url.uuid == uuid)
        url = self.db.scalar(statement)

        if url is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="url not found")

        short_code = url.short_code

        self.db.delete(url)
        self.db.commit()

        try:
            redis_client.delete(f"url:{short_code}")
        except RedisError:
            print('Failed to remove cache')


    def activate_url(self, short_code) -> Url:
        statement = select(Url).where(Url.short_code == short_code)
        url = self.db.scalar(statement)

        if url is None: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "url not found.")

        if url.isActive:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="url is already active.")

        url.isActive = True

        self.db.commit()
        try:
            redis_client.delete(f"url:{url.short_code}")
        except RedisError:
            print("FAILED TO REMOVE CACHED DATA FROM REDIS")

        self.db.refresh(url)
        return url