from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.common.errors import (
    AppError,
    ErrorProveedor,
    app_error_handler,
    provider_error_handler,
    validation_error_handler,
)
from app.common.limite_cuerpo import LimiteDeCuerpo
from app.common.logger import logger
from app.config.constantes import MARGEN_MULTIPART_BYTES, MAX_BYTES_SUBIDA
from app.config.settings import settings
from app.config.version import VERSION
from app.routers import catalogo, documentos, preguntas


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"{settings.APP_NAME} started — docs at /docs")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # vacía = ningún origen cruzado; se abre por .env
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LimiteDeCuerpo, max_bytes=MAX_BYTES_SUBIDA + MARGEN_MULTIPART_BYTES)

# ── Exception handlers ─────────────────────────────────────────────────────────

# Starlette tipa el handler como (Request | WebSocket, Exception); cada uno de estos recibe solo la
# subclase con la que se registra y solo peticiones HTTP. El ignore cubre esa diferencia de firma.
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]  # ver nota
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]  # ver nota
app.add_exception_handler(ErrorProveedor, provider_error_handler)  # type: ignore[arg-type]  # ver nota

# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(catalogo.router, prefix="/api")
app.include_router(documentos.router, prefix="/api")
app.include_router(preguntas.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.APP_NAME}
