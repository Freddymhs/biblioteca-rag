"""Auditoría de la FASE_5, parte I (I1–I12). Cada test falla sin su arreglo.

La pieza central es `_todo_lo_exportado`: nombres, atributos, eventos (con su traza de pila) y
`status.description` de TODOS los spans terminados, sin importar quién los emitió.
"""

from collections.abc import Sequence
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from redis import Redis
from redis.exceptions import RedisError

from app.config.constantes import ENCABEZADO_API_KEY, PREFIJO_USO
from app.config.settings import settings
from app.providers.embeddings import obtener_proveedor_embeddings
from app.providers.limites import Limitador, obtener_limitador
from main import app
from tests.dobles import ClasificadorDoble, LLMGrabador, proveedor_doble

pytestmark = pytest.mark.usefixtures("biblioteca_publica")
MARCA = "marca-zzz-que-no-debe-salir"
# Un número que solo puede llegar a una traza si se vuelcan los parámetros del SQL.
VALOR_MARCADO = 0.4242424242


def _todo_lo_exportado(spans: Sequence[ReadableSpan]) -> str:
    partes: list[str] = []
    for span in spans:
        partes.append(span.name)
        partes.append(span.status.description or "")
        valores: list[Any] = [*(span.attributes or {}).values()]
        for evento in span.events:
            partes.append(evento.name)
            valores.extend((evento.attributes or {}).values())
        partes.extend(str(valor) for valor in valores)
    return "\n".join(partes)


@pytest.fixture
def sin_propagar(anonimo: TestClient) -> TestClient:
    """El mismo cliente anónimo, pero un 500 vuelve como respuesta y no como excepción."""
    return TestClient(app, raise_server_exceptions=False)


# ── I1: una excepción no vuelca su mensaje en la traza ────────────────────────


def test_i1_un_error_de_postgres_no_deja_el_sql_ni_sus_parametros(
    sin_propagar: TestClient, trazas: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Postgres real: un vector de otra dimensión hace fallar la consulta de pgvector, y el error
    de SQLAlchemy trae el SQL y los parámetros (el vector de la pregunta)."""
    from app.services import publico

    monkeypatch.setattr(publico, "embeber_pregunta", lambda *_: [VALOR_MARCADO] * 3)

    respuesta = sin_propagar.get("/api/publico/buscar", params={"q": "olivo"})
    texto = _todo_lo_exportado(trazas.get_finished_spans())

    assert respuesta.status_code == 500
    assert len(trazas.get_finished_spans()) >= 2  # denominador
    assert str(VALOR_MARCADO) not in texto
    assert "SELECT" not in texto and "trozo" not in texto.lower().replace("buscar_trozos", "")


class EmbeddingsQueFallan:
    def embed_query(self, _texto: str) -> list[float]:
        raise RuntimeError(MARCA)

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        raise RuntimeError(MARCA)


@pytest.mark.parametrize("etapa", ["embeber", "redactar"])
def test_i1_una_excepcion_en_cada_etapa_deja_solo_su_tipo(
    sin_propagar: TestClient,
    trazas: InMemorySpanExporter,
    llm: LLMGrabador,
    monkeypatch: pytest.MonkeyPatch,
    etapa: str,
) -> None:
    if etapa == "embeber":
        doble = proveedor_doble(cliente=EmbeddingsQueFallan())  # type: ignore[arg-type]
        app.dependency_overrides[obtener_proveedor_embeddings] = lambda: doble
    else:

        def falla(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError(MARCA)

        monkeypatch.setattr(LLMGrabador, "_generate", falla)

    sin_propagar.post("/api/publico/preguntas", json={"pregunta": "¿Kc del olivo?"})
    spans = trazas.get_finished_spans()

    assert spans and MARCA not in _todo_lo_exportado(spans)
    assert any((s.attributes or {}).get("error.type") == "RuntimeError" for s in spans)


def test_i1_los_engines_ocultan_los_parametros() -> None:
    from app.config.database import engine, obtener_engine_publico

    assert engine.hide_parameters and obtener_engine_publico().hide_parameters


# ── I2: el SDK de MCP no exporta texto del visitante ni acepta su traceparent ──

TRAZA_DEL_CLIENTE = "4bf92f3577b34da6a3ce929d0e0e4736"


def test_i2_el_nombre_de_tool_y_el_traceparent_del_cliente_no_llegan_a_la_traza(
    url_mcp: str, anonimo: TestClient, trazas: InMemorySpanExporter
) -> None:
    pedido = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": MARCA,
            "arguments": {},
            "_meta": {"traceparent": f"00-{TRAZA_DEL_CLIENTE}-00f067aa0ba902b7-01"},
        },
    }
    cabeceras = {"Accept": "application/json, text/event-stream"}

    httpx.post(url_mcp, json=pedido, headers=cabeceras)
    spans = trazas.get_finished_spans()

    assert spans  # al menos el span HTTP de la petición
    assert MARCA not in _todo_lo_exportado(spans)
    assert all(format(s.context.trace_id, "032x") != TRAZA_DEL_CLIENTE for s in spans if s.context)


def test_i2_solo_se_exportan_spans_del_trazador_de_la_app(
    url_mcp: str, anonimo: TestClient, trazas: InMemorySpanExporter
) -> None:
    import asyncio

    from mcp import Client

    async def buscar() -> Any:
        async with Client(url_mcp) as cliente:
            return await cliente.call_tool("buscar", {"pregunta": "olivo"})

    asyncio.run(buscar())
    alcances = {
        s.instrumentation_scope.name for s in trazas.get_finished_spans() if s.instrumentation_scope
    }

    assert alcances == {"biblioteca-rag"}


# ── I12: 401 y 413 tampoco dejan nada ─────────────────────────────────────────


def test_i12_un_401_no_deja_la_clave_ni_el_cuerpo(
    sin_propagar: TestClient, trazas: InMemorySpanExporter
) -> None:
    sin_propagar.post("/api/espacios", json={"slug": MARCA}, headers={ENCABEZADO_API_KEY: MARCA})
    sin_propagar.post("/api/publico/preguntas", content=MARCA.encode() * 2000)

    texto = _todo_lo_exportado(trazas.get_finished_spans())

    assert len(trazas.get_finished_spans()) == 2 and MARCA not in texto


# ── I3, I4: la métrica no cambia la respuesta, y «servida» es servida ─────────


class RedisQueNoCuentaUso:
    """Redis real, salvo que todo pipeline que toque una clave `uso:` falla al ejecutarse."""

    def __init__(self, real: Redis) -> None:
        self._real = real

    def pipeline(self) -> "TuberiaQueNoCuentaUso":
        return TuberiaQueNoCuentaUso(self._real.pipeline())

    def mget(self, claves: list[str]) -> Any:
        return self._real.mget(claves)


class TuberiaQueNoCuentaUso:
    def __init__(self, real: Any) -> None:
        self._real = real
        self._toca_uso = False

    def incr(self, clave: str) -> None:
        self._toca_uso = self._toca_uso or clave.startswith(f"{PREFIJO_USO}:")
        self._real.incr(clave)

    def expire(self, *argumentos: Any, **opciones: Any) -> None:
        self._real.expire(*argumentos, **opciones)

    def ttl(self, clave: str) -> None:
        self._real.ttl(clave)

    def execute(self) -> Any:
        if self._toca_uso:
            raise RedisError("contador de uso caído")
        return self._real.execute()


def test_i3_si_falla_el_contador_la_consulta_y_el_429_salen_igual(
    anonimo: TestClient, redis_limpio: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    falla_uso = Limitador(cast(Redis, RedisQueNoCuentaUso(redis_limpio)))
    app.dependency_overrides[obtener_limitador] = lambda: falla_uso
    monkeypatch.setattr(settings, "LIMITE_BUSQUEDAS_POR_MINUTO", 1)

    valida = anonimo.get("/api/publico/buscar", params={"q": "olivo"})
    excedida = anonimo.get("/api/publico/buscar", params={"q": "olivo"})

    assert (valida.status_code, excedida.status_code) == (200, 429)


def test_i4_un_502_del_proveedor_no_cuenta_como_servida(
    anonimo: TestClient, client: TestClient, llm: LLMGrabador
) -> None:
    llm.falla = True

    anonimo.post("/api/publico/preguntas", json={"pregunta": "¿Kc del olivo?"})
    uso = client.get("/api/uso", params={"dias": 1}).json()[0]

    assert uso["respuestas"] == 0


# ── I5: nombres de span acotados ─────────────────────────────────────────────


def test_i5_el_span_usa_la_plantilla_de_la_ruta_y_no_la_url_cruda(
    client: TestClient, sin_propagar: TestClient, trazas: InMemorySpanExporter
) -> None:
    client.get("/api/espacios/intereses/colecciones/agricultura/documentos")
    sin_propagar.get(f"/{MARCA}/admin.php")  # un escáner: cae en el montaje del MCP
    client.get(f"/api/espacios/{MARCA}/colecciones")  # 404 con slug inventado (con clave)

    nombres = [s.name for s in trazas.get_finished_spans() if s.kind.name == "SERVER"]

    assert nombres == [
        "GET /api/espacios/{espacio}/colecciones/{coleccion}/documentos",
        "GET (sin ruta)",
        "GET /api/espacios/{espacio}/colecciones",
    ]


# ── I6: la herramienta se anota solo si es una del paquete ───────────────────


def test_i6_una_herramienta_inventada_por_el_llm_no_queda_en_la_traza(
    client: TestClient,
    trazas: InMemorySpanExporter,
    clasificador: ClasificadorDoble,
) -> None:
    from app.config.constantes import AtributoTraza, TipoDecision
    from app.providers.estructurado import Decision

    cuerpo = {"slug": "facturas", "nombre": "F", "paquete": "facturas"}
    client.post("/api/espacios/intereses/colecciones", json=cuerpo)
    clasificador.decision = Decision(tipo=TipoDecision.CALCULO, herramienta=MARCA)

    client.post(
        "/api/preguntas",
        json={"pregunta": "¿Cuánto?", "espacio": "intereses", "coleccion": "facturas"},
    )
    spans = trazas.get_finished_spans()
    clasificar = next(s for s in spans if s.name == "clasificar")

    assert MARCA not in _todo_lo_exportado(spans)
    assert (clasificar.attributes or {}).get(AtributoTraza.DECISION) == "calculo"


# ── I9: describir una imagen no es redactar una respuesta ────────────────────


def test_i9_la_vision_tiene_su_propia_etapa(
    client: TestClient, trazas: InMemorySpanExporter
) -> None:
    from tests.pdf_minimo import FIGURA, pdf_minimo

    archivo = ("figura.pdf", pdf_minimo([FIGURA]))
    client.post(
        "/api/espacios/intereses/colecciones/agricultura/documentos", files={"archivo": archivo}
    )
    nombres = {s.name for s in trazas.get_finished_spans()}

    assert "describir_imagen" in nombres and "redactar" not in nombres


# ── I11: LangSmith apagado por construcción ──────────────────────────────────


def test_i11_langsmith_no_se_enciende_aunque_lo_pida_el_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from langsmith import utils

    import app.providers.llm  # noqa: F401 — al importarse, apaga LangSmith

    for variable in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        monkeypatch.setenv(variable, "true")
    # LangSmith cachea el entorno (`lru_cache`, oculto tras sus `@overload`): sin vaciarlo, el
    # test vería el valor viejo y no podría fallar.
    vaciar_cache = cast(Any, utils.get_env_var).cache_clear
    vaciar_cache()
    try:
        encendido = utils.tracing_is_enabled()
    finally:
        vaciar_cache()

    assert encendido is False


def test_i11_compose_lo_apaga_en_el_entorno_de_la_api_y_el_worker() -> None:
    from pathlib import Path

    import yaml

    raiz = Path(__file__).resolve().parent.parent
    entorno = yaml.safe_load((raiz / "docker-compose.yml").read_text())["x-app"]["environment"]

    assert entorno["LANGSMITH_TRACING"] == "false" and entorno["LANGCHAIN_TRACING_V2"] == "false"
