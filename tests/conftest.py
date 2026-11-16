import os
import secrets
import socket
import threading
import time
from collections.abc import Generator

import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from redis import Redis
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.observabilidad import crear_proveedor_trazas  # no lee settings: puede ir antes

PGVECTOR_IMAGE = "pgvector/pgvector:pg16"

# El contenedor arranca ANTES de importar la app: settings, engine y alembic/env.py leen
# DATABASE_URL al importarse, y así los tres apuntan a la misma base desechable.
_postgres = PostgresContainer(PGVECTOR_IMAGE, driver="psycopg")
_postgres.start()
os.environ["DATABASE_URL"] = _postgres.get_connection_url()
# G10: 32 caracteres o más, como exige la app.
os.environ["API_KEY"] = "clave-de-test-con-32-caracteres-o-mas"
# G6: lo público entra con un usuario con login del grupo público (se crea tras migrar, en
# `engine`), igual que en producción; nunca con el respaldo de desarrollo.
URL_PUBLICA_TEST = make_url(_postgres.get_connection_url()).set(
    username="biblioteca_web_test", password=secrets.token_urlsafe(16)
)
os.environ["DATABASE_URL_PUBLICA"] = URL_PUBLICA_TEST.render_as_string(hide_password=False)
os.environ["PERMITIR_PUBLICO_SIN_USUARIO"] = "false"
# Trazas (FASE_5): un proveedor con exportador en memoria, antes de importar la app; el fixture
# `trazas` lo vacía en cada test. La app no configura otro: TRAZAS_OTLP_URL va vacía.
EXPORTADOR_TRAZAS = InMemorySpanExporter()
# El mismo proveedor que producción (con su filtro de spans de la app), solo con otro exportador.
trace.set_tracer_provider(crear_proveedor_trazas(SimpleSpanProcessor(EXPORTADOR_TRAZAS)))
os.environ["TRAZAS_OTLP_URL"] = ""
# Los tests no dependen del .env local: lo que el código lee al importarse se fija aquí.
os.environ["CORS_ORIGINS"] = "[]"

# Imports tardíos intencionales: dependen de DATABASE_URL, fijada justo arriba.
from app.cli.usuario_publico import crear_usuario_publico  # noqa: E402
from app.config.constantes import ENCABEZADO_API_KEY, ROL_PUBLICO  # noqa: E402
from app.config.database import engine as app_engine  # noqa: E402
from app.config.database import get_db, get_db_publico  # noqa: E402
from app.providers.embeddings import (  # noqa: E402
    ProveedorDeEmbeddings,
    obtener_proveedor_embeddings,
)
from app.providers.estructurado import (  # noqa: E402
    obtener_clasificador,
    obtener_fabrica_extractor,
)
from app.providers.limites import Limitador, obtener_limitador  # noqa: E402
from app.providers.llm import obtener_llm  # noqa: E402
from app.providers.vision import obtener_vision  # noqa: E402
from app.services import catalogo  # noqa: E402
from app.services.documentos import fijar_licencia  # noqa: E402
from app.services.ingesta import ingestar  # noqa: E402
from main import app  # noqa: E402
from tests.dobles import (  # noqa: E402
    BIBLIOTECA_PUBLICA,
    DESCRIPCION_VISION,
    LICENCIA_DOBLE,
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
    crear_usuario_publico(app_engine, os.environ["DATABASE_URL_PUBLICA"])
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
        yield TestClient(app, headers={ENCABEZADO_API_KEY: os.environ["API_KEY"]})
    finally:
        app.dependency_overrides.clear()


# ── Lo público (FASE_4): API pública y MCP ────────────────────────────────────


@pytest.fixture
def biblioteca_publica(db: Session) -> None:
    """Ver BIBLIOTECA_PUBLICA: un documento público y dos que no lo son."""
    proveedor = proveedor_doble()
    for espacio in sorted({fila[0] for fila in BIBLIOTECA_PUBLICA}):
        catalogo.crear_espacio(db, espacio, espacio)
    for espacio, coleccion, publica in sorted({fila[:3] for fila in BIBLIOTECA_PUBLICA}):
        catalogo.crear_coleccion(db, espacio, coleccion, coleccion)
        catalogo.publicar_coleccion(db, espacio, coleccion, publica)
    for espacio, coleccion, _, archivo, contenido, verificada in BIBLIOTECA_PUBLICA:
        destino = catalogo.obtener_coleccion(db, espacio, coleccion)
        ingerido = ingestar(db, destino, archivo, contenido.encode(), proveedor, vision=None)
        fijar_licencia(db, destino, ingerido.documento.id, LICENCIA_DOBLE, verificada)


@pytest.fixture
def redis_limpio(redis_url: str) -> Redis:
    redis = Redis.from_url(redis_url)
    redis.flushdb()
    return redis


@pytest.fixture
def anonimo(client: TestClient, db: Session, redis_limpio: Redis) -> TestClient:
    """Sin API key, con la sesión bajo el rol público (RLS real) y el límite en un Redis real."""

    def sesion_publica() -> Generator[Session, None, None]:
        db.execute(text(f"SET ROLE {ROL_PUBLICO}"))
        try:
            yield db
        finally:
            db.execute(text("RESET ROLE"))

    app.dependency_overrides[get_db_publico] = sesion_publica
    app.dependency_overrides[obtener_limitador] = lambda: Limitador(redis_limpio)
    return TestClient(app)


# ── Servidor real (MCP y cuerpos en trozos) ──────────────────────────────────

ESPERA_ARRANQUE_SEGUNDOS = 10.0
INTERVALO_SONDEO_SEGUNDOS = 0.05


def _puerto_libre() -> int:
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        return sonda.getsockname()[1]


@pytest.fixture(scope="session")
def url_servidor(engine: Engine) -> Generator[str, None, None]:
    """uvicorn real en un hilo, una vez por sesión: el session manager del MCP corre una sola
    vez por instancia. Las sustituciones de `app.dependency_overrides` valen también aquí."""
    puerto = _puerto_libre()
    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + ESPERA_ARRANQUE_SEGUNDOS
    while not servidor.started and time.monotonic() < limite:
        time.sleep(INTERVALO_SONDEO_SEGUNDOS)
    assert servidor.started, "uvicorn no arrancó"
    try:
        yield f"http://127.0.0.1:{puerto}"
    finally:
        servidor.should_exit = True
        hilo.join()


@pytest.fixture
def url_mcp(url_servidor: str) -> str:
    return f"{url_servidor}/mcp"


@pytest.fixture
def trazas() -> InMemorySpanExporter:
    """Los spans que terminen durante el test (también los del servidor uvicorn de la sesión)."""
    EXPORTADOR_TRAZAS.clear()
    return EXPORTADOR_TRAZAS
