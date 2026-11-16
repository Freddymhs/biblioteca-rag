"""Tope del cuerpo HTTP ANTES de que la app lo lea (G1).

FastAPI parsea el cuerpo (y vuelca un multipart a disco) antes de resolver las dependencias del
endpoint: cualquier chequeo dentro del endpoint llega tarde. Este middleware rechaza por
`Content-Length` sin leer nada y, si no hay `Content-Length` (chunked), cuenta los bytes a medida
que la app los pide: al pasarse, corta la lectura y responde 413 en lugar de la app.
"""

import re
from http import HTTPStatus

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LimiteDeCuerpo:
    def __init__(
        self, app: ASGIApp, max_bytes: int, limites_por_ruta: dict[str, int] | None = None
    ) -> None:
        """`limites_por_ruta`: patrón de ruta (regex) → máximo propio. Gana el primero que calza."""
        self.app = app
        self.max_bytes = max_bytes
        self.limites_por_ruta = [
            (re.compile(patron), limite) for patron, limite in (limites_por_ruta or {}).items()
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limite = self._limite(scope["path"])
        rechazo = self._rechazo(Headers(scope=scope).get("content-length"), limite)
        if rechazo is not None:
            await rechazo(scope, desconectado, send)
            return
        await _CuerpoContado(self.app, limite)(scope, receive, send)

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
            return _demasiado_grande(limite)
        return None


class _CuerpoContado:
    """Una petición: cuenta lo recibido; al pasarse del tope, la app ve una desconexión y lo
    que intente responder se reemplaza por el 413."""

    def __init__(self, app: ASGIApp, limite: int) -> None:
        self.app = app
        self.limite = limite
        self.recibidos = 0
        self.excedido = False
        self.respuesta_enviada = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def recibir() -> Message:
            if self.excedido:
                return {"type": "http.disconnect"}
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                self.recibidos += len(mensaje.get("body", b""))
                if self.recibidos > self.limite:
                    self.excedido = True
                    return {"type": "http.disconnect"}
            return mensaje

        async def enviar(mensaje: Message) -> None:
            if not self.excedido:
                await send(mensaje)
                return
            if not self.respuesta_enviada:  # lo que la app quiso responder no sale
                self.respuesta_enviada = True
                await _demasiado_grande(self.limite)(scope, desconectado, send)

        await self.app(scope, recibir, enviar)
        if self.excedido and not self.respuesta_enviada:
            await _demasiado_grande(self.limite)(scope, desconectado, send)


async def desconectado() -> Message:
    """`receive` para responder sin leer más: el JSONResponse de Starlette escucha la desconexión
    llamando a `receive`, y con el original drenaría el resto del cuerpo."""
    return {"type": "http.disconnect"}


def _demasiado_grande(limite: int) -> JSONResponse:
    return JSONResponse(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={"error": f"El cuerpo supera el máximo de {limite} bytes"},
    )
