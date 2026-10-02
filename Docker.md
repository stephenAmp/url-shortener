# Run the URL shortener with Docker Compose

This starts the FastAPI app, PostgreSQL, and Redis together for local development. Run these commands from the project root with Docker running.

## 1. Keep local files out of the image

Create `.dockerignore`:

```text
.env
.env.*
.venv/
.git/
**/__pycache__/
```

This keeps your local credentials and virtual environment out of the build context.

## 2. Build the API image

Create `Dockerfile` (capital **D**):

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

It installs Python dependencies and copies the API and Alembic migrations.

## 3. Set a local database password

Add this to your ignored `.env` file, replacing the example with your own alphanumeric password:

```env
POSTGRES_PASSWORD=your_local_password
```

Compose reads this value from `.env`. Your existing local `DATABASE_URL` and `REDIS_URL` can stay there; the Compose file gives the API container its own URLs.

## 4. Connect the three services

Create `compose.yaml`:

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+psycopg://app:${POSTGRES_PASSWORD}@db:5432/urls"
      REDIS_URL: "redis://redis:6379/0"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  db:
    image: postgres:17
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: urls
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d urls"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7

volumes:
  postgres_data:
```

Inside Compose, `db` and `redis` are the service hostnames; `localhost` inside the API container would point to the API itself. The named PostgreSQL volume keeps database data when containers restart. The API waits until PostgreSQL is healthy.

## 5. Start and migrate

Stop any local FastAPI server using port 8000. Then run:

```sh
docker compose config -q
docker compose up -d --build
docker compose exec api alembic upgrade head
```

The first command checks the Compose file. The second builds and starts the services. The third creates or updates the tables in the **Compose database**, which is separate from your existing local PostgreSQL database.

## 6. Check it

```sh
curl http://localhost:8000/health
curl -i http://localhost:8000/urls/
```

The health route should return `{"status":"ok"}`. The URL list should return **200** with a paginated JSON response; it uses PostgreSQL for the list and Redis for rate limiting.

## Common commands

```sh
docker compose logs --tail=20 api  # See API errors
docker compose up -d --build api    # Rebuild API after code changes
docker compose down                 # Stop containers; keep database data
```

## If the API fails during import

We hit `AttributeError: 'MappedColumn' object has no attribute 'UUID'` in `app/db/models/url.py`. The model field named `uuid` hid the imported `uuid` module. Fix it by using an alias:

```python
import uuid as uuid_lib

# Use uuid_lib.UUID in the Url and Click annotations.
# Use uuid_lib.uuid4 for their UUID defaults.
uuid: Mapped[uuid_lib.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4
)
```

Also change `Click.url_uuid` to `Mapped[uuid_lib.UUID]`, then rebuild the API with `docker compose up -d --build api`.
