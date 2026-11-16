"""MCP público por HTTP (tarea 4.7): cualquier agente consulta; Hermes es uno más.

Solo dos tools, de solo lectura: `buscar` (fragmentos con cita, sin LLM) y `preguntar`
(respuesta redactada). Usan lo mismo que /api/publico: la sesión del rol público (RLS), los
mismos servicios y el mismo límite por IP. Las dependencias se resuelven con los
`dependency_overrides` de la app FastAPI: un test sustituye una pieza y vale para REST y MCP.
"""

from collections.abc import Callable, Generator, MutableMapping
from contextlib import contextmanager
from dataclasses import asdict
from functools import partial
from inspect import isgenerator
from typing import Annotated, Any

import anyio
from fastapi import Request
from langchain_core.language_models import BaseChatModel
from mcp.server import MCPServer
from mcp.server._otel import OpenTelemetryMiddleware  # privado: si se mueve, falla aquí
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from opentelemetry.context import Context as OtelContext
from pydantic import Field
from sqlalchemy.orm import Session

from app.common.errors import AppError, unprocessable
from app.config.constantes import MAX_LARGO_PREGUNTA, MAX_LARGO_SLUG, PATRON_SLUG, UsoPublico
from app.config.database import get_db_publico
from app.config.version import VERSION
from app.observabilidad import contexto_de, dentro_de
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.limites import (
    IP_DESCONOCIDA,
    CuposLLM,
    Limitador,
    ip_cliente,
    obtener_cupos_llm,
    obtener_limitador,
)
from app.providers.llm import obtener_llm
from app.schemas.pregunta import CitaSalida, RespuestaSalida
from app.schemas.publico import MENSAJE_COLECCION_SIN_ESPACIO, BusquedaSalida
from app.services import publico
from app.services.publico import Visitante

NOMBRE_SERVIDOR = "biblioteca-rag"
INSTRUCCIONES = (
    "Biblioteca técnica (agricultura y más) con cita. `buscar` devuelve fragmentos con su "
    "documento, páginas y licencia, sin redactar nada; `preguntar` redacta una respuesta corta "
    "con cita o dice «no lo sé». Solo lectura y solo colecciones públicas; uso limitado por IP."
)
SOLO_LECTURA = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)

Pregunta = Annotated[str, Field(min_length=1, max_length=MAX_LARGO_PREGUNTA)]
Slug = Annotated[str | None, Field(max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG)]
# `Any`: las dependencias de FastAPI tienen firmas distintas (sesión, proveedor, LLM, limitador).
Sustituciones = MutableMapping[Callable[..., Any], Callable[..., Any]]


def crear_servidor_mcp(sustituciones: Sustituciones) -> MCPServer:
    servidor = MCPServer(NOMBRE_SERVIDOR, version=VERSION, instructions=INSTRUCCIONES)
    # I2: el SDK trae un middleware de OpenTelemetry encendido que nombra el span con el nombre de
    # tool del cliente (texto libre) y toma su `_meta.traceparent`. Fuera (el SDK lo documenta así:
    # «drop it from this list to opt out»); las etapas ya cuelgan de la traza HTTP propia.
    servidor.middleware[:] = [
        capa for capa in servidor.middleware if not isinstance(capa, OpenTelemetryMiddleware)
    ]

    # `Any`: devuelve lo que devuelva la dependencia resuelta (ver `Sustituciones`).
    @contextmanager
    def resuelta(dependencia: Callable[..., Any]) -> Generator[Any, None, None]:
        """Llama la dependencia (o su sustituta); si es un generador, como FastAPI: lo cierra."""
        valor = sustituciones.get(dependencia, dependencia)()
        if not isgenerator(valor):
            yield valor
            return
        try:
            yield next(valor)
        finally:
            valor.close()

    @contextmanager
    def visitante(uso: UsoPublico, ip: str) -> Generator[Visitante, None, None]:
        """El límite por minuto antes de todo; las cuotas, después de validar (en el servicio)."""
        limitador: Limitador
        cupos: CuposLLM
        with resuelta(obtener_limitador) as limitador, resuelta(obtener_cupos_llm) as cupos:
            limitador.consumir(uso, ip)
            yield Visitante(ip=ip, limitador=limitador, cupos=cupos)

    def buscar_ahora(
        pregunta: str, espacio: str | None, coleccion: str | None, ip: str
    ) -> BusquedaSalida:
        _exigir_espacio(espacio, coleccion)
        db: Session
        proveedor: ProveedorDeEmbeddings
        with (
            visitante(UsoPublico.BUSQUEDA, ip) as quien,
            resuelta(get_db_publico) as db,
            resuelta(obtener_proveedor_embeddings) as proveedor,
        ):
            citas = publico.buscar_publico(db, pregunta, espacio, coleccion, proveedor, quien)
        return BusquedaSalida(fragmentos=[CitaSalida.model_validate(asdict(c)) for c in citas])

    def preguntar_ahora(
        pregunta: str, espacio: str | None, coleccion: str | None, ip: str
    ) -> RespuestaSalida:
        _exigir_espacio(espacio, coleccion)
        db: Session
        proveedor: ProveedorDeEmbeddings
        llm: BaseChatModel
        with (
            visitante(UsoPublico.RESPUESTA, ip) as quien,
            resuelta(get_db_publico) as db,
            resuelta(obtener_proveedor_embeddings) as proveedor,
            resuelta(obtener_llm) as llm,
        ):
            respuesta = publico.preguntar_publico(
                db, pregunta, espacio, coleccion, proveedor, llm, quien
            )
        return RespuestaSalida.model_validate(asdict(respuesta))

    @servidor.tool(title="Buscar fragmentos con cita", annotations=SOLO_LECTURA)
    async def buscar(
        pregunta: Pregunta, ctx: Context, espacio: Slug = None, coleccion: Slug = None
    ) -> BusquedaSalida:
        """Fragmentos de documentos públicos con su cita (documento, páginas, licencia). Sin LLM.
        Sin espacio ni colección busca en todas las colecciones públicas."""
        trabajo = partial(buscar_ahora, pregunta, espacio, coleccion, _ip(ctx))
        return await _ejecutar(trabajo, _contexto(ctx))

    @servidor.tool(title="Preguntar con cita", annotations=SOLO_LECTURA)
    async def preguntar(
        pregunta: Pregunta, ctx: Context, espacio: Slug = None, coleccion: Slug = None
    ) -> RespuestaSalida:
        """Respuesta corta redactada con los fragmentos públicos, con cita, o «no lo sé».
        Más limitada que `buscar`: usa un LLM."""
        trabajo = partial(preguntar_ahora, pregunta, espacio, coleccion, _ip(ctx))
        return await _ejecutar(trabajo, _contexto(ctx))

    return servidor


async def _ejecutar[T](trabajo: Callable[[], T], traza: OtelContext | None) -> T:
    """Corre el trabajo (bloqueante: base, embeddings, LLM) en un hilo, dentro de la traza de la
    petición HTTP. Un error de dominio (404, 422, 429, 503) vuelve al agente con su código y
    mensaje: el SDK oculta cualquier otra excepción tras «Error executing tool»."""

    def en_la_traza() -> T:
        with dentro_de(traza):
            return trabajo()

    try:
        return await anyio.to_thread.run_sync(en_la_traza)
    except AppError as error:
        raise ToolError(f"{error.status_code.value}: {error.message}") from error


def _exigir_espacio(espacio: str | None, coleccion: str | None) -> None:
    if coleccion is not None and espacio is None:
        raise unprocessable(MENSAJE_COLECCION_SIN_ESPACIO)


def _contexto(ctx: Context) -> OtelContext | None:
    peticion = ctx.request_context.request
    return contexto_de(peticion) if isinstance(peticion, Request) else None


def _ip(ctx: Context) -> str:
    """La misma IP que usa el límite de la API REST (sin HTTP, p. ej. en memoria: desconocida)."""
    peticion = ctx.request_context.request
    return ip_cliente(peticion) if isinstance(peticion, Request) else IP_DESCONOCIDA
