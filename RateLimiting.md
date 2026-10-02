# Rate limiting in this URL shortener

Rate limiting uses Redis to count requests from each client IP during the current minute. It helps prevent one client from sending too many requests to an endpoint.

## 1. What you need

Use the Redis setup in [Redis.md](Redis.md): start Redis, set `REDIS_URL` in `.env`, and install the packages in `requirements.txt`. Rate limiting uses the same `redis_client` from `app/core/redis.py`; it needs no separate setup.

## 2. Where it runs

`rate_limit(action, limit)` lives in `app/api/routes/urls.py`. It returns a FastAPI dependency. The routes currently use it like this:

| Endpoint | Action | Limit per IP, per minute |
| --- | --- | ---: |
| `POST /urls/` | `urls:create` | 10 |
| `GET /urls/` | `urls:list` | 20 |
| `GET /urls/{short_code}` | `urls:redirect` | 100 |

For example:

```python
@router.post(
    "/",
    dependencies=[Depends(rate_limit("urls:create", 10))],
)
def create_url(...):
    ...
```

FastAPI runs the dependency before the route function. Give each endpoint a unique action name so its counter does not mix with another endpoint's counter.

## 3. How the function works

This is the `rate_limit` function from `app/api/routes/urls.py`:

```python
def rate_limit(action: str, limit: int):
    def check_rate(request: Request) -> None:
        # TODO: At deployment, verify this is the real client IP behind the trusted proxy.
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
                detail="Service temporarily unavailable",
            )

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(60 - now % 60)},
            )

    return check_rate
```

1. `rate_limit("urls:create", 10)` makes a check for that action and limit. FastAPI runs the returned `check_rate` function before the route.
2. The key contains the action, client IP, and current minute (`now // 60`). Each IP gets a separate counter for each action, and the counter resets when the minute changes.
3. Redis `INCR` adds one request. `EXPIRE` removes the old key after 120 seconds. The pipeline runs both commands in one transaction; the key's minute number defines the rate-limit window.
4. If the count is over the limit, the function raises **429**. `Retry-After` gives the seconds left in the current minute. If Redis is unavailable, it raises **503** and the route does not run.

## 4. Add the limit to another route

Add a dependency to that route's decorator, using its own action name and limit:

```python
dependencies=[Depends(rate_limit("urls:analytics", 30))]
```

This helper currently lives with the URL routes. Move it to a shared module if another router needs it.

## 5. Check it locally

At the start of a fresh minute, send 11 valid requests to `POST /urls/` from the same device. The first 10 should create URLs; the 11th should return 429 and create nothing. Its `Retry-After` value should be between 1 and 60 seconds.

To inspect the current counter, use the action, your client IP, and the current minute in the key:

```sh
redis-cli GET 'rate:urls:create:127.0.0.1:MINUTE_NUMBER'
```

**Deployment TODO:** verify that `request.client.host` contains the real client IP when the API runs behind a trusted proxy. Otherwise, different users may share one limit.
