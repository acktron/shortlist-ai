from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import settings


def normalize_database_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername == "postgresql+psycopg2":
        url = url.set(drivername="postgresql+psycopg")
    if url.host and url.host.endswith(".neon.tech") and "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"})
    return url


engine=create_engine(normalize_database_url(settings.database_url),pool_pre_ping=True); SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
class Base(DeclarativeBase): pass
def get_db() -> Generator[Session,None,None]:
    db=SessionLocal()
    try: yield db
    finally: db.close()

