"""API key para todo lo privado (escribir, administrar y leer lo no público). Tarea 4.5."""

from hashlib import sha256
from secrets import compare_digest

from fastapi import Security
from fastapi.security import APIKeyHeader
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.common.errors import AppError, service_unavailable, unauthorized
from app.common.limite_cuerpo import desconectado
from app.common.rutas import es_ruta_privada
from app.config.constantes import ENCABEZADO_API_KEY
from app.config.settings import settings

esquema_api_key = APIKeyHeader(
    name=ENCABEZADO_API_KEY,
    auto_error=False,  # sin encabezado, el mensaje y el 401 los pone esta dependencia
    description="La que define API_KEY en .env. Sin ella solo responde /api/publico y /mcp.",
)


def exigir_api_key(recibida: str | None = Security(esquema_api_key)) -> None:
    """Dependencia: documenta la clave en el OpenAPI y es la segunda barrera (la primera es el
    middleware, que rechaza antes de leer el cuerpo)."""
    validar_clave(recibida)


def validar_clave(recibida: str | None) -> None:
    esperada = settings.API_KEY.get_secret_value()
    if not esperada:
        # Fail-closed: un despliegue sin clave no queda abierto, queda cerrado.
        raise service_unavailable("La API no tiene API_KEY configurada: lo privado está cerrado")
    if recibida is None or not _iguales(recibida, esperada):
        raise unauthorized(f"Falta la API key o no es válida (encabezado {ENCABEZADO_API_KEY})")


def _iguales(recibida: str, esperada: str) -> bool:
    """Tiempo constante; el hash previo iguala los largos para no filtrar el de la clave."""
    return compare_digest(sha256(recibida.encode()).digest(), sha256(esperada.encode()).digest())


class ExigirClaveAntesDelCuerpo:
    """G1: sin clave válida, 401/503 sin leer un byte del cuerpo (FastAPI lo lee antes de
    resolver las dependencias). Va por dentro de CORS: el preflight no lleva la clave."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and es_ruta_privada(scope["path"]):
            try:
                validar_clave(Headers(scope=scope).get(ENCABEZADO_API_KEY))
            except AppError as error:
                respuesta = JSONResponse(
                    status_code=error.status_code, content={"error": error.message}
                )
                await respuesta(scope, desconectado, send)  # sin leer el cuerpo
                return
        await self.app(scope, receive, send)
