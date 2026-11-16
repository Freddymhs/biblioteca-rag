"""Trazas por pregunta (tarea 5.1): OpenTelemetry con spans manuales, exportadas por OTLP a un
Jaeger local (perfil `trazas` de compose). Sin URL configurada, los spans se crean y se descartan.

Privacidad (decisión de la fase): ninguna traza guarda el texto de una pregunta ni una IP. Solo
lo necesario para ver qué trozos se usaron, cuánto tardó cada etapa y con qué proveedor. Por eso
no se usa la auto-instrumentación HTTP: registraría la URL con su query, y en
`GET /api/publico/buscar?q=…` la query ES la pregunta.
"""

import re
from collections.abc import Generator, Sequence
from contextlib import contextmanager

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace import Span as SdkSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, StatusCode, format_trace_id
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.common.rutas import es_ruta_privada, es_ruta_publica
from app.config.constantes import (
    CLAVE_CONTEXTO_TRAZA,
    ENCABEZADO_TRAZA,
    ESPERA_VACIADO_TRAZAS_MS,
    NOMBRE_SERVICIO_TRAZAS,
    NOMBRE_SIN_RUTA,
    RUTA_MCP,
    AlcanceTraza,
    AtributoTraza,
)

trazador = trace.get_tracer(NOMBRE_SERVICIO_TRAZAS)


def configurar_trazas(url_otlp: str) -> None:
    """Una vez por proceso, al arrancar. Sin URL no se configura nada (los spans no se guardan)."""
    if not url_otlp:
        return
    exportador = BatchSpanProcessor(OTLPSpanExporter(endpoint=url_otlp))
    trace.set_tracer_provider(crear_proveedor_trazas(exportador))


def crear_proveedor_trazas(procesador: SpanProcessor) -> TracerProvider:
    """El proveedor global, con el filtro de abajo: lo usan producción y los tests por igual."""
    proveedor = TracerProvider(resource=Resource.create({"service.name": NOMBRE_SERVICIO_TRAZAS}))
    proveedor.add_span_processor(SoloDeLaApp(procesador))
    return proveedor


class SoloDeLaApp(SpanProcessor):
    """I2: exporta solo los spans del trazador de esta app. Las bibliotecas que emiten con el
    proveedor global (el SDK de MCP guarda el nombre de tool que manda el cliente; FastAPI, la
    query) quedan fuera por construcción, también las que se instalen mañana."""

    def __init__(self, procesador: SpanProcessor) -> None:
        self._procesador = procesador

    def on_start(self, span: SdkSpan, parent_context: Context | None = None) -> None:
        if _es_de_la_app(span):
            self._procesador.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        if _es_de_la_app(span):
            self._procesador.on_end(span)

    def shutdown(self) -> None:
        self._procesador.shutdown()

    def force_flush(self, timeout_millis: int = ESPERA_VACIADO_TRAZAS_MS) -> bool:
        return self._procesador.force_flush(timeout_millis)


def _es_de_la_app(span: ReadableSpan) -> bool:
    alcance = span.instrumentation_scope
    return alcance is not None and alcance.name == NOMBRE_SERVICIO_TRAZAS


# Lo que OpenTelemetry acepta como valor de atributo; None se omite.
Atributo = str | bool | int | float | Sequence[int] | Sequence[float] | Sequence[str] | None
Atributos = dict[str, Atributo]


@contextmanager
def etapa(nombre: str, atributos: Atributos | None = None) -> Generator[Span, None, None]:
    """Un span por etapa (embeber, buscar, redactar…): su duración es la latencia de la etapa."""
    with _span_sin_mensajes(nombre) as span:
        _poner(span, atributos or {})
        yield span


@contextmanager
def _span_sin_mensajes(
    nombre: str, tipo: trace.SpanKind = trace.SpanKind.INTERNAL
) -> Generator[Span, None, None]:
    """I1: OpenTelemetry guarda por defecto el mensaje y la pila de una excepción. Un error de
    base trae el SQL con sus parámetros (el vector de la pregunta); el de un proveedor, lo que
    él quiera. Aquí, ante un error, solo su tipo y el estado ERROR sin descripción."""
    with trazador.start_as_current_span(
        nombre, kind=tipo, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield span
        except BaseException as error:
            span.set_attribute(AtributoTraza.TIPO_ERROR, type(error).__qualname__)
            span.set_status(StatusCode.ERROR)
            raise


def anotar(atributos: Atributos) -> None:
    """Agrega atributos al span en curso (p. ej. los trozos usados, al terminar la etapa)."""
    _poner(trace.get_current_span(), atributos)


def _poner(span: Span, atributos: Atributos) -> None:
    for clave, valor in atributos.items():
        if valor is not None:
            span.set_attribute(clave, valor)


class TrazaHTTP:
    """Span raíz por petición, nombrado con la PLANTILLA de la ruta (I5: nunca la URL cruda, que
    trae slugs, ids o lo que invente un escáner; nunca la query) y el código de respuesta.
    Devuelve el id de la traza en `X-Traza-Id`: con él se busca en Jaeger qué pasó."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta: str = scope["path"]
        metodo: str = scope["method"]
        # El nombre definitivo se pone al final: la ruta se resuelve dentro de la app.
        with _span_sin_mensajes(metodo, trace.SpanKind.SERVER) as span:
            span.set_attribute(AtributoTraza.ALCANCE, _alcance(ruta))
            contexto = span.get_span_context()
            # Para quien atienda la petición fuera de este contexto (las tools del MCP corren en
            # el task group del SDK): lo recupera con `contexto_de` y lo reactiva con `dentro_de`.
            scope.setdefault("state", {})[CLAVE_CONTEXTO_TRAZA] = otel_context.get_current()

            async def enviar(mensaje: Message) -> None:
                if mensaje["type"] == "http.response.start":
                    span.set_attribute(AtributoTraza.CODIGO_HTTP, mensaje["status"])
                    if contexto.is_valid:
                        cabeceras = MutableHeaders(scope=mensaje)
                        cabeceras.append(ENCABEZADO_TRAZA, format_trace_id(contexto.trace_id))
                await send(mensaje)

            try:
                await self.app(scope, receive, enviar)
            finally:
                span.update_name(f"{metodo} {_plantilla(scope)}")


def _plantilla(scope: Scope) -> str:
    """La ruta tal como se declaró (`/api/espacios/{espacio}/…`). El montaje del MCP atiende
    cualquier ruta: si no es /mcp, un nombre fijo."""
    ruta: str = scope["path"]
    resuelta = scope.get("route")
    plantilla: str = getattr(resuelta, "path_format", "")
    patron: re.Pattern[str] | None = getattr(resuelta, "path_regex", None)
    if plantilla and patron is not None:
        # FastAPI guarda la plantilla sin el prefijo de `include_router` (/api): el prefijo es
        # el tramo inicial que deja a la regex calzar con el resto (estático, no del cliente).
        for corte in (i for i, letra in enumerate(ruta) if letra == "/"):
            if patron.match(ruta[corte:]):
                return ruta[:corte] + plantilla
        return plantilla
    return RUTA_MCP if ruta == RUTA_MCP else NOMBRE_SIN_RUTA


def contexto_de(conexion: HTTPConnection) -> Context | None:
    return conexion.scope.get("state", {}).get(CLAVE_CONTEXTO_TRAZA)


@contextmanager
def dentro_de(contexto: Context | None) -> Generator[None, None, None]:
    """Las etapas que corran aquí cuelgan de la traza de la petición."""
    if contexto is None:
        yield
        return
    token = otel_context.attach(contexto)
    try:
        yield
    finally:
        otel_context.detach(token)


def _alcance(ruta: str) -> str:
    if es_ruta_publica(ruta):
        return AlcanceTraza.PUBLICO
    if es_ruta_privada(ruta):
        return AlcanceTraza.PRIVADO
    return AlcanceTraza.OTRO
