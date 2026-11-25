"""Tarea 5.1: para cualquier respuesta se ve qué trozos usó, cuánto tardó cada etapa y con qué
proveedor; y ninguna traza guarda el texto de una pregunta ni una IP."""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import format_trace_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constantes import (
    ENCABEZADO_IP_CLOUDFLARE,
    ENCABEZADO_TRAZA,
    AtributoTraza,
    EtapaTraza,
    TipoDecision,
)
from app.config.settings import settings
from app.models import Documento, Trozo
from app.providers.estructurado import Decision
from tests.dobles import (
    FACTURA_OLIVOS,
    MODELO_DOBLE,
    ClasificadorDoble,
    ExtractorDoble,
)

pytestmark = pytest.mark.usefixtures("biblioteca_publica")
SECRETO = "pregunta-secreta-xyz"
IP_VISITANTE = "203.0.113.77"


def _id_traza(span: ReadableSpan) -> str:
    assert span.context is not None
    return format_trace_id(span.context.trace_id)


# `Any`: los valores de atributo de OpenTelemetry (str, int, listas…).
def _atributos(span: ReadableSpan) -> Mapping[str, Any]:
    return span.attributes or {}


def _de_la_traza(trazas: InMemorySpanExporter, id_traza: str) -> dict[str, ReadableSpan]:
    return {s.name: s for s in trazas.get_finished_spans() if _id_traza(s) == id_traza}


def _trozos_de(db: Session, archivo: str) -> set[int]:
    consulta = select(Trozo.id).join(Documento).where(Documento.nombre_archivo == archivo)
    return set(db.scalars(consulta))


def _duracion(span: ReadableSpan) -> int:
    assert span.start_time is not None and span.end_time is not None
    return span.end_time - span.start_time


def test_una_respuesta_trae_su_traza_con_etapas_trozos_y_proveedor(
    client: TestClient, trazas: InMemorySpanExporter, db: Session
) -> None:
    cuerpo = {"pregunta": "¿Kc del olivo?", "espacio": "intereses", "coleccion": "agricultura"}

    respuesta = client.post("/api/preguntas", json=cuerpo)
    spans = _de_la_traza(trazas, respuesta.headers[ENCABEZADO_TRAZA])

    etapas = {EtapaTraza.PREGUNTAR, EtapaTraza.EMBEBER, EtapaTraza.BUSCAR, EtapaTraza.REDACTAR}
    assert etapas <= spans.keys()
    assert all(_duracion(spans[e]) > 0 for e in etapas)
    usados = _atributos(spans[EtapaTraza.PREGUNTAR])[AtributoTraza.TROZOS_USADOS]
    assert set(usados) == _trozos_de(db, "olivo.txt")
    candidatos = _atributos(spans[EtapaTraza.BUSCAR])[AtributoTraza.TROZOS_CANDIDATOS]
    assert set(usados) <= set(candidatos)
    assert len(_atributos(spans[EtapaTraza.BUSCAR])[AtributoTraza.DISTANCIAS]) == len(candidatos)
    assert _atributos(spans[EtapaTraza.EMBEBER])[AtributoTraza.PROVEEDOR_EMBEDDINGS] == MODELO_DOBLE
    assert _atributos(spans[EtapaTraza.REDACTAR])[AtributoTraza.PROVEEDOR_LLM]


def _todo_el_texto(spans: Sequence[ReadableSpan]) -> str:
    """Nombres, estado, atributos y eventos de todos los spans, como un solo texto."""
    partes: list[str] = []
    for span in spans:
        partes.append(span.name)
        partes.append(span.status.description or "")  # I12: también el estado
        valores: list[Any] = [*(span.attributes or {}).values()]
        for evento in span.events:
            partes.append(evento.name)
            valores.extend((evento.attributes or {}).values())
        partes.extend(str(valor) for valor in valores)
    return "\n".join(partes)


def test_ni_la_pregunta_ni_la_ip_de_un_anonimo_quedan_en_la_traza(
    anonimo: TestClient, trazas: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CONFIAR_EN_CF_CONNECTING_IP", True)
    cabeceras = {ENCABEZADO_IP_CLOUDFLARE: IP_VISITANTE}

    anonimo.post("/api/publico/preguntas", json={"pregunta": f"{SECRETO} olivo"}, headers=cabeceras)
    anonimo.get("/api/publico/buscar", params={"q": f"{SECRETO} olivo"}, headers=cabeceras)
    texto = _todo_el_texto(trazas.get_finished_spans())

    assert len(trazas.get_finished_spans()) >= 6  # denominador: hubo trazas que revisar
    assert SECRETO not in texto and IP_VISITANTE not in texto
    assert "GET /api/publico/buscar" in texto  # la ruta sí, su query no


def test_la_busqueda_publica_dice_que_trozos_devolvio(
    anonimo: TestClient, trazas: InMemorySpanExporter, db: Session
) -> None:
    respuesta = anonimo.get("/api/publico/buscar", params={"q": "olivo"})
    spans = _de_la_traza(trazas, respuesta.headers[ENCABEZADO_TRAZA])

    usados = _atributos(spans[EtapaTraza.BUSCAR_PUBLICO])[AtributoTraza.TROZOS_USADOS]
    assert set(usados) == _trozos_de(db, "olivo.txt")
    assert {EtapaTraza.EMBEBER, EtapaTraza.BUSCAR} <= spans.keys()


def test_un_calculo_traza_la_decision_la_herramienta_y_sus_trozos(
    client: TestClient,
    trazas: InMemorySpanExporter,
    extractor: ExtractorDoble,
    clasificador: ClasificadorDoble,
) -> None:
    client.post(
        "/api/espacios/intereses/colecciones",
        json={"slug": "facturas", "nombre": "F", "paquete": "facturas"},
    )
    extractor.datos = FACTURA_OLIVOS
    subida = client.post(
        "/api/espacios/intereses/colecciones/facturas/documentos",
        files={"archivo": ("f.txt", b"Factura 4521")},
    ).json()
    client.post(f"/api/extracciones/{subida['extraccion_id']}/confirmacion", json=FACTURA_OLIVOS)
    clasificador.decision = Decision(tipo=TipoDecision.CALCULO, herramienta="total_facturado")
    trazas.clear()

    respuesta = client.post(
        "/api/preguntas",
        json={"pregunta": "¿Cuánto?", "espacio": "intereses", "coleccion": "facturas"},
    )
    spans = _de_la_traza(trazas, respuesta.headers[ENCABEZADO_TRAZA])

    assert _atributos(spans[EtapaTraza.CLASIFICAR])[AtributoTraza.DECISION] == "calculo"
    calculo = _atributos(spans[EtapaTraza.CALCULAR])
    assert calculo[AtributoTraza.HERRAMIENTA] == "total_facturado"
    assert len(calculo[AtributoTraza.TROZOS_USADOS]) == 1


def test_el_mcp_tambien_traza_sus_etapas(
    url_mcp: str, anonimo: TestClient, trazas: InMemorySpanExporter
) -> None:
    async def buscar() -> Any:
        async with Client(url_mcp) as cliente:
            return await cliente.call_tool("buscar", {"pregunta": f"{SECRETO} olivo"})

    asyncio.run(buscar())
    spans = trazas.get_finished_spans()
    publica = next(s for s in spans if s.name == EtapaTraza.BUSCAR_PUBLICO)
    # El cliente hace varios POST /mcp (initialize, notificación, tools/call): uno de ellos es
    # la petición de la tool, y su traza es la de la etapa.
    trazas_http = {_id_traza(s) for s in spans if s.name == "POST /mcp"}

    assert _atributos(publica)[AtributoTraza.TROZOS_USADOS]
    assert _id_traza(publica) in trazas_http
    assert SECRETO not in _todo_el_texto(spans)
