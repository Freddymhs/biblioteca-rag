from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator
from app.config.settings import settings


# Engine — equivalent to the Prisma client
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Session factory — like a DB connection pool
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class all SQLAlchemy models inherit from."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a DB session per request.
    Equivalent to Prisma's request-scoped client in Express.

    Usage in a router:
        def my_route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
