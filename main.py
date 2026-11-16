from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.telemetry import TelemetryConfig
from mcp.server.transport_security import TransportSecuritySettings

from app.common.auth import ExigirClaveAntesDelCuerpo, exigir_api_key
from app.common.errors import (
    AppError,
    ErrorProveedor,
    app_error_handler,
    provider_error_handler,
    validation_error_handler,
)
from app.common.limite_cuerpo import LimiteDeCuerpo
from app.common.logger import logger
from app.config.constantes import (
    MARGEN_MULTIPART_BYTES,
    MAX_BYTES_CUERPO_PUBLICO,
    MAX_BYTES_LOTE,
    MAX_BYTES_SUBIDA,
    PATRON_RUTA_LOTES,
    PATRONES_RUTA_PUBLICA,
)
from app.config.database import obtener_engine_publico, verificar_usuario_publico
from app.config.settings import settings
from app.config.version import VERSION
from app.mcp_publico import crear_servidor_mcp
from app.observabilidad import TrazaHTTP, configurar_trazas
from app.routers import catalogo, documentos, extracciones, preguntas, publico, trabajos, uso


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"{settings.APP_NAME} started — docs at /docs, MCP at /mcp")
    configurar_trazas(settings.TRAZAS_OTLP_URL)
    # G6/G7: sin usuario público válido la API no arranca (el respaldo de desarrollo, con aviso).
    engine_publico = obtener_engine_publico()
    if settings.DATABASE_URL_PUBLICA.get_secret_value():
        verificar_usuario_publico(engine_publico)
    # El MCP montado no corre su propio lifespan: lo corre la app que lo monta (doc del SDK).
    async with servidor_mcp.session_manager.run():
        yield


TELEMETRIA_NATIVA_APAGADA: TelemetryConfig = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}

app = FastAPI(
    title=settings.APP_NAME,
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # FASE_5: la instrumentación nativa de FastAPI guarda `url.query`, y en
    # /api/publico/buscar?q=… eso es la pregunta del visitante. Apagada entera; el span HTTP lo
    # crea TrazaHTTP con la ruta sin query.
    telemetry=TELEMETRIA_NATIVA_APAGADA,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# Orden: el último agregado es el más externo. Queda TrazaHTTP → LimiteDeCuerpo → CORS → clave →
# app: toda petición tiene su span (también un 413 o un 401), el preflight lo responde CORS y la
# clave se pide antes de que nadie lea el cuerpo (G1).
app.add_middleware(ExigirClaveAntesDelCuerpo)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # vacía = ningún origen cruzado; se abre por .env
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    LimiteDeCuerpo,
    max_bytes=MAX_BYTES_SUBIDA + MARGEN_MULTIPART_BYTES,
    limites_por_ruta={
        PATRON_RUTA_LOTES: MAX_BYTES_LOTE,
        **dict.fromkeys(PATRONES_RUTA_PUBLICA, MAX_BYTES_CUERPO_PUBLICO),
    },
)

# FASE_5: el span raíz de cada petición, por fuera de todo.
app.add_middleware(TrazaHTTP)

# ── Exception handlers ─────────────────────────────────────────────────────────

# Starlette tipa el handler como (Request | WebSocket, Exception); cada uno de estos recibe solo la
# subclase con la que se registra y solo peticiones HTTP. El ignore cubre esa diferencia de firma.
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]  # ver nota
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]  # ver nota
app.add_exception_handler(ErrorProveedor, provider_error_handler)  # type: ignore[arg-type]  # ver nota

# ── Routes ─────────────────────────────────────────────────────────────────────

# Todo lo privado exige la API key, también leer: ahí están las colecciones personales.
PRIVADO = [Depends(exigir_api_key)]
for router_privado in (catalogo, documentos, preguntas, trabajos, extracciones, uso):
    app.include_router(router_privado.router, prefix="/api", dependencies=PRIVADO)
# Lo público: sin clave, con el rol público de Postgres y límite de uso.
app.include_router(publico.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}


# ── MCP público (tarea 4.7) ────────────────────────────────────────────────────

# Sin estado y en JSON: cada llamada es independiente (sirve detrás de varios procesos).
# Va al final: `Mount("/")` captura toda ruta que no haya atendido nadie antes.
servidor_mcp = crear_servidor_mcp(app.dependency_overrides)
app.mount(
    "/",
    servidor_mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=settings.MCP_HOSTS_PERMITIDOS,
            allowed_origins=settings.MCP_ORIGENES_PERMITIDOS,
        ),
    ),
)
