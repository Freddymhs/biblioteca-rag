"""Tarea 3.2: LangGraph clasifica «cálculo vs significado». Un cálculo usa una herramienta SQL
fija (respuesta determinista, sin LLM); un significado, la búsqueda semántica. Nunca SQL libre."""

import pytest
from fastapi.testclient import TestClient

from app.config.constantes import TipoDecision
from app.providers.estructurado import Decision
from tests.dobles import FACTURA_OLIVOS, ClasificadorDoble, ExtractorDoble, LLMGrabador

URL = "/api/preguntas"
COLECCION = "/api/espacios/intereses/colecciones/facturas"
FACTURA_PODAS = {**FACTURA_OLIVOS, "numero": "77", "fecha": "2026-05-02", "emisor": "Podas del Sur"}
FACTURA_PODAS["total"] = "50000"


@pytest.fixture(autouse=True)
def facturas_confirmadas(client: TestClient, extractor: ExtractorDoble) -> None:
    client.post("/api/espacios", json={"slug": "intereses", "nombre": "Intereses"})
    client.post(
        "/api/espacios/intereses/colecciones",
        json={"slug": "facturas", "nombre": "Facturas", "paquete": "facturas"},
    )
    for nombre, datos in (("olivos.txt", FACTURA_OLIVOS), ("podas.txt", FACTURA_PODAS)):
        extractor.datos = datos
        archivo = (nombre, f"Factura {datos['numero']} de {datos['emisor']}".encode())
        subida = client.post(f"{COLECCION}/documentos", files={"archivo": archivo}).json()
        client.post(f"/api/extracciones/{subida['extraccion_id']}/confirmacion", json=datos)


def _preguntar(client: TestClient, pregunta: str, coleccion: str | None = "facturas") -> dict:
    cuerpo = {"pregunta": pregunta, "espacio": "intereses", "coleccion": coleccion}
    respuesta = client.post(URL, json=cuerpo)
    assert respuesta.status_code == 200, respuesta.json()
    return respuesta.json()


def test_un_calculo_usa_la_herramienta_sql_sin_llamar_al_llm(
    client: TestClient, clasificador: ClasificadorDoble, llm: LLMGrabador
) -> None:
    clasificador.decision = Decision(tipo=TipoDecision.CALCULO, herramienta="total_facturado")

    cuerpo = _preguntar(client, "¿Cuánto facturé en total?")

    assert (cuerpo["ruta"], cuerpo["herramienta"], cuerpo["sabe"]) == (
        "sql",
        "total_facturado",
        True,
    )
    assert "169.000 CLP en 2 facturas" in cuerpo["respuesta"]
    assert {cita["origen"] for cita in cuerpo["citas"]} == {"datos"}
    assert len(cuerpo["citas"]) == 2
    assert llm.recibidos == []  # la respuesta la escribe el formateador, no el LLM


def test_los_argumentos_del_clasificador_filtran_por_parametro(
    client: TestClient, clasificador: ClasificadorDoble
) -> None:
    clasificador.decision = Decision(
        tipo=TipoDecision.CALCULO,
        herramienta="total_facturado",
        argumentos={"desde": "2026-05-01", "hasta": "2026-05-31"},
    )

    cuerpo = _preguntar(client, "¿Cuánto facturé en mayo?")

    assert "50.000 CLP en 1 factura." in cuerpo["respuesta"]
    assert [cita["documento"] for cita in cuerpo["citas"]] == ["podas.txt"]


def test_un_significado_va_por_la_busqueda_semantica(
    client: TestClient, clasificador: ClasificadorDoble, llm: LLMGrabador
) -> None:
    llm.respuesta = "Es una factura de Podas del Sur [1]."

    cuerpo = _preguntar(client, "¿Qué empresa hizo las podas?")

    assert (cuerpo["ruta"], cuerpo["herramienta"]) == ("semantica", None)
    assert clasificador.preguntas == ["¿Qué empresa hizo las podas?"]


@pytest.mark.parametrize(
    "decision",
    [
        Decision(tipo=TipoDecision.CALCULO, herramienta="borrar_todo"),
        Decision(tipo=TipoDecision.CALCULO, herramienta=None),
        Decision(
            tipo=TipoDecision.CALCULO, herramienta="total_facturado", argumentos={"desde": "ayer"}
        ),
        Decision(
            tipo=TipoDecision.CALCULO,
            herramienta="facturado_por_emisor",
            argumentos={"limite": 999},
        ),
    ],
    ids=["herramienta-inexistente", "sin-herramienta", "fecha-invalida", "limite-fuera-de-rango"],
)
def test_una_decision_invalida_cae_en_la_busqueda_semantica(
    client: TestClient, clasificador: ClasificadorDoble, decision: Decision
) -> None:
    clasificador.decision = decision

    cuerpo = _preguntar(client, "¿Cuánto facturé?")

    assert cuerpo["ruta"] == "semantica"


def test_sin_coleccion_o_sin_paquete_no_se_clasifica(
    client: TestClient, clasificador: ClasificadorDoble
) -> None:
    client.post("/api/espacios/intereses/colecciones", json={"slug": "notas", "nombre": "Notas"})

    sin_coleccion = _preguntar(client, "¿Cuánto facturé?", coleccion=None)
    sin_paquete = _preguntar(client, "¿Cuánto facturé?", coleccion="notas")

    assert (sin_coleccion["ruta"], sin_paquete["ruta"]) == ("semantica", "semantica")
    assert clasificador.preguntas == []


def test_el_clasificador_no_tiene_por_donde_devolver_sql() -> None:
    assert set(Decision.model_fields) == {"tipo", "herramienta", "argumentos"}


def test_el_esquema_que_ve_el_llm_obliga_a_nombrar_una_herramienta_del_paquete() -> None:
    """Medido con llama3.2:3b: con `herramienta` opcional respondía «calculo» y la omitía."""
    from app.dominio import obtener_paquete
    from app.providers.estructurado import esquema_de_decision

    esquema = esquema_de_decision(obtener_paquete("facturas")).model_json_schema()

    assert set(esquema["required"]) == {"tipo", "herramienta", "argumentos"}
    opciones = esquema["properties"]["herramienta"]["anyOf"][0]["enum"]
    assert opciones == [
        "total_facturado",
        "cantidad_de_facturas",
        "facturado_por_emisor",
        "factura_mas_alta",
    ]
