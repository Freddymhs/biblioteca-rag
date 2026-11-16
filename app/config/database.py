from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings

# Un engine por proceso: administra el pool de conexiones a Postgres.
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Fábrica de sesiones; cada petición HTTP o archivo de la CLI abre la suya.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base de todos los modelos; su `metadata` es lo que compara Alembic."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión por petición, cerrada al terminar.

    Uso en un router: `def ruta(db: Session = Depends(get_db)) -> ...`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
