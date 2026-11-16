"""Rechaza por `Content-Length` ANTES de leer el cuerpo.

FastAPI parsea el multipart (y lo vuelca a disco) antes de resolver las dependencias del endpoint:
cualquier chequeo dentro del endpoint llega tarde. Un cuerpo sin `Content-Length` (chunked) pasa
este filtro; lo frenan después: en la subida de un archivo, `deteccion.detectar` (lee hasta el
máximo + 1); en los lotes, `routers/trabajos._guardar_copias`, que cuenta los bytes al copiar.
"""

import re
from http import HTTPStatus

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class LimiteDeCuerpo:
    def __init__(
        self, app: ASGIApp, max_bytes: int, limites_por_ruta: dict[str, int] | None = None
    ) -> None:
        """`limites_por_ruta`: patrón de ruta (regex) → máximo propio, ej. la subida de lotes."""
        self.app = app
        self.max_bytes = max_bytes
        self.limites_por_ruta = [
            (re.compile(patron), limite) for patron, limite in (limites_por_ruta or {}).items()
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            limite = self._limite(scope["path"])
            rechazo = self._rechazo(Headers(scope=scope).get("content-length"), limite)
            if rechazo is not None:
                await rechazo(scope, receive, send)
                return
        await self.app(scope, receive, send)

    def _limite(self, ruta: str) -> int:
        for patron, limite in self.limites_por_ruta:
            if patron.match(ruta):
                return limite
        return self.max_bytes

    def _rechazo(self, content_length: str | None, limite: int) -> JSONResponse | None:
        if content_length is None:
            return None
        if not content_length.isdigit():
            return JSONResponse(
                status_code=HTTPStatus.BAD_REQUEST, content={"error": "Content-Length inválido"}
            )
        if int(content_length) > limite:
            return JSONResponse(
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                content={"error": f"El cuerpo supera el máximo de {limite} bytes"},
            )
        return None
