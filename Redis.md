# Redis in this URL shortener

Redis keeps a temporary copy of each active short URL's destination. PostgreSQL remains the source of truth for URLs and click counts.

## 1. Start Redis

Install Redis, then start it if it is not already running:

```sh
redis-server
```

In another terminal, run `redis-cli ping`. A working server replies `PONG`.

## 2. Configure the API

The `redis` Python package is in `requirements.txt`. Install dependencies with `pip install -r requirements.txt`.

Add this to `.env` alongside `DATABASE_URL`:

```env
REDIS_URL=redis://localhost:6379/0
```

In `app/core/config.py`, Pydantic reads that value from `.env`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

In `app/core/redis.py`, the app creates one synchronous client:

```python
from redis import Redis
from app.core.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)
```

`decode_responses=True` makes Redis return text instead of bytes. The timeouts prevent an unavailable Redis server from holding up redirects for long.

## 3. Read and write a cached URL

The cache key is `url:{short_code}`. The value is JSON containing the URL's ID and destination. In `app/services/url.py`:

```python
import json

# Read: a cache hit returns JSON text; a miss returns None.
raw = redis_client.get(f"url:{short_code}")
if raw:
    cached = json.loads(raw)  # JSON text -> Python dict

# Write after loading and validating an active URL from PostgreSQL.
redis_client.set(
    f"url:{short_code}",
    json.dumps({"uuid": str(url.uuid), "original_url": url.original_url}),
    ex=ttl,
)
```

`json.dumps` turns the dictionary into text Redis can store; `json.loads` turns that text back into a dictionary. `str(url.uuid)` is needed because a UUID cannot be serialized to JSON directly. The actual read path also checks the JSON fields and UUID before using them.

`ex=ttl` sets the expiry in seconds. This project uses at most 60 seconds and shortens the TTL if the URL expires sooner.

## 4. Redirect safely

For `GET /urls/{short_code}`, `get_redirect_url` tries Redis first. On a miss, it loads the URL from PostgreSQL, checks that it exists, is active, and has not expired, then caches it. On a hit, it gets the ID and destination from Redis.

**Every request still updates PostgreSQL:** a guarded `UPDATE` checks that the URL is active and unexpired, increments `click_count`, and saves the click record in the same commit. If the update affects no row, the service deletes the stale cache entry and rejects the redirect.

## 5. Remove stale entries

After deactivating, activating, or deleting a URL, the service calls:

```python
redis_client.delete(f"url:{short_code}")
```

The next redirect therefore reads fresh data. The lookup code can fall back to PostgreSQL if Redis is unavailable, but the redirect route's [rate limiter](RateLimiting.md) currently returns 503 before lookup when Redis is down. Restarting Redis does not remove URLs or click history.

## Quick check

Start the API with `uvicorn app.main:app --reload`, then open an active short URL twice. Both requests should redirect, and its click count should increase by two. While the cache entry exists, inspect it with:

```sh
redis-cli GET url:YOUR_SHORT_CODE
redis-cli TTL url:YOUR_SHORT_CODE
```

An absent entry is normal after its TTL expires or the URL changes.
