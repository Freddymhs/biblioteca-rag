import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

PGVECTOR_IMAGE = "pgvector/pgvector:pg16"

# El contenedor arranca ANTES de importar la app: settings, engine y alembic/env.py leen
# DATABASE_URL al importarse, y así los tres apuntan a la misma base desechable.
_postgres = PostgresContainer(PGVECTOR_IMAGE, driver="psycopg")
_postgres.start()
os.environ["DATABASE_URL"] = _postgres.get_connection_url()
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# Los tests no dependen del .env local: lo que el código lee al importarse se fija aquí.
os.environ["CORS_ORIGINS"] = "[]"

# Imports tardíos intencionales: dependen de DATABASE_URL, fijada justo arriba.
from app.config.database import engine as app_engine  # noqa: E402
from app.config.database import get_db  # noqa: E402
from app.providers.embeddings import (  # noqa: E402
    ProveedorDeEmbeddings,
    obtener_proveedor_embeddings,
)
from app.providers.estructurado import (  # noqa: E402
    obtener_clasificador,
    obtener_fabrica_extractor,
)
from app.providers.llm import obtener_llm  # noqa: E402
from app.providers.vision import obtener_vision  # noqa: E402
from main import app  # noqa: E402
from tests.dobles import (  # noqa: E402
    DESCRIPCION_VISION,
    ClasificadorDoble,
    ExtractorDoble,
    LLMGrabador,
    proveedor_doble,
)


def pytest_sessionfinish() -> None:
    _postgres.stop()


@pytest.fixture(scope="session")
def redis_url() -> Generator[str, None, None]:
    """Redis desechable, compartido por los tests que necesitan la cola real."""
    with RedisContainer("redis:7-alpine") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}"


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Base real con el esquema de las migraciones (no `create_all`): prueba Alembic de paso."""
    command.upgrade(Config("alembic.ini"), "head")
    return app_engine


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """Sesión dentro de una transacción que se revierte al final: cada test parte limpio.

    `create_savepoint` hace que los `commit()` del código bajo prueba cierren un savepoint
    en vez de la transacción exterior.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def proveedor() -> ProveedorDeEmbeddings:
    return proveedor_doble()


@pytest.fixture
def llm() -> LLMGrabador:
    return LLMGrabador()


@pytest.fixture
def vision() -> LLMGrabador:
    return LLMGrabador(respuesta=DESCRIPCION_VISION)


@pytest.fixture
def extractor() -> ExtractorDoble:
    return ExtractorDoble()


@pytest.fixture
def clasificador() -> ClasificadorDoble:
    return ClasificadorDoble()


@pytest.fixture
def client(
    db: Session,
    proveedor: ProveedorDeEmbeddings,
    llm: LLMGrabador,
    vision: LLMGrabador,
    extractor: ExtractorDoble,
    clasificador: ClasificadorDoble,
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[obtener_proveedor_embeddings] = lambda: proveedor
    app.dependency_overrides[obtener_llm] = lambda: llm
    app.dependency_overrides[obtener_vision] = lambda: vision
    app.dependency_overrides[obtener_fabrica_extractor] = lambda: lambda: extractor
    app.dependency_overrides[obtener_clasificador] = lambda: clasificador
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
