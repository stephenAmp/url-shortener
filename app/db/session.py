from sqlalchemy import create_engine;
from sqlalchemy.orm import sessionmaker, Session;
from collections.abc import Generator

from app.core.config import settings;

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True
)

sessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:

    db  = sessionLocal()
    try:
        yield db
    finally:
        db.close()