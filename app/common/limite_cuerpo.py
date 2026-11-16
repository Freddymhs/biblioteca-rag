"""Rechaza por `Content-Length` ANTES de leer el cuerpo.

FastAPI parsea el multipart (y lo vuelca a disco) antes de resolver las dependencias del endpoint:
cualquier chequeo dentro del endpoint llega tarde. Un cuerpo sin `Content-Length` (chunked) pasa, y
lo frena la segunda barrera de `deteccion.detectar`.
"""

from http import HTTPStatus

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class LimiteDeCuerpo:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            rechazo = self._rechazo(Headers(scope=scope).get("content-length"))
            if rechazo is not None:
                await rechazo(scope, receive, send)
                return
        await self.app(scope, receive, send)

    def _rechazo(self, content_length: str | None) -> JSONResponse | None:
        if content_length is None:
            return None
        if not content_length.isdigit():
            return JSONResponse(
                status_code=HTTPStatus.BAD_REQUEST, content={"error": "Content-Length inválido"}
            )
        if int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                content={"error": f"El cuerpo supera el máximo de {self.max_bytes} bytes"},
            )
        return None
