"""Tarea 3.1: extracción → formulario (JSON Schema) → confirmación. Solo se embebe lo confirmado."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Trozo
from tests.dobles import FACTURA_OLIVOS, ExtractorDoble, RespuestaHTTP

BASE = "/api/espacios/intereses/colecciones/facturas"
TEXTO_FACTURA = (
    "FACTURA N° 4521\nAgricola Los Olivos SpA\nFecha: 12-03-2026\nTOTAL: $119.000".encode()
)


@pytest.fixture(autouse=True)
def coleccion_con_paquete(client: TestClient) -> None:
    client.post("/api/espacios", json={"slug": "intereses", "nombre": "Intereses"})
    respuesta = client.post(
        "/api/espacios/intereses/colecciones",
        json={"slug": "facturas", "nombre": "Facturas", "paquete": "facturas"},
    )
    assert respuesta.status_code == 201, respuesta.json()


def _subir(client: TestClient, contenido: bytes = TEXTO_FACTURA) -> RespuestaHTTP:
    return client.post(f"{BASE}/documentos", files={"archivo": ("factura.txt", contenido)})


def _trozos(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Trozo)) or 0


def test_paquete_desconocido_es_422(client: TestClient) -> None:
    respuesta = client.post(
        "/api/espacios/intereses/colecciones", json={"slug": "x", "nombre": "x", "paquete": "nada"}
    )

    assert respuesta.status_code == 422


def test_subir_a_una_coleccion_con_paquete_crea_una_extraccion_pendiente_sin_embeber(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    respuesta = _subir(client)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert cuerpo["trozos"] == 0
    assert cuerpo["extraccion_id"] is not None
    assert "4521" in extractor.textos[0]  # el extractor recibió el texto del documento
    assert _trozos(db) == 0


def test_el_formulario_es_el_json_schema_con_la_propuesta(client: TestClient) -> None:
    extraccion_id = _subir(client).json()["extraccion_id"]

    formulario = client.get(f"/api/extracciones/{extraccion_id}/formulario").json()

    assert formulario["estado"] == "pendiente"
    assert formulario["paquete"] == "facturas"
    assert {"numero", "fecha", "emisor", "total"} <= set(formulario["json_schema"]["required"])
    assert formulario["propuesta"]["numero"] == "4521"
    assert formulario["errores"] == []


def test_una_propuesta_invalida_llega_al_formulario_con_sus_errores(
    client: TestClient, extractor: ExtractorDoble
) -> None:
    extractor.datos = {**FACTURA_OLIVOS, "fecha": "1203-03-26"}  # lo que leyó llama3.2:3b
    extractor.errores = ["fecha: año 1203 fuera de 1990–2100"]

    formulario = client.get(
        f"/api/extracciones/{_subir(client).json()['extraccion_id']}/formulario"
    ).json()

    assert formulario["propuesta"]["fecha"] == "1203-03-26"
    assert formulario["errores"] == ["fecha: año 1203 fuera de 1990–2100"]


def test_confirmar_datos_invalidos_es_422_y_no_embebe(client: TestClient, db: Session) -> None:
    extraccion_id = _subir(client).json()["extraccion_id"]

    respuesta = client.post(
        f"/api/extracciones/{extraccion_id}/confirmacion",
        json={**FACTURA_OLIVOS, "fecha": "1203-03-26"},
    )

    assert respuesta.status_code == 422
    assert _trozos(db) == 0


def test_confirmar_embebe_solo_lo_confirmado(client: TestClient, db: Session) -> None:
    extraccion_id = _subir(client).json()["extraccion_id"]
    corregido = {**FACTURA_OLIVOS, "emisor": "Agrícola Los Olivos SpA"}

    respuesta = client.post(f"/api/extracciones/{extraccion_id}/confirmacion", json=corregido)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert (cuerpo["estado"], cuerpo["trozos"]) == ("confirmada", 1)
    trozo = db.scalars(select(Trozo)).one()
    assert trozo.origen.value == "datos"
    assert "Agrícola Los Olivos SpA" in trozo.texto  # lo corregido, no lo propuesto
    assert "119.000 CLP" in trozo.texto


def test_confirmar_dos_veces_es_409(client: TestClient) -> None:
    extraccion_id = _subir(client).json()["extraccion_id"]
    url = f"/api/extracciones/{extraccion_id}/confirmacion"
    client.post(url, json=FACTURA_OLIVOS)

    assert client.post(url, json=FACTURA_OLIVOS).status_code == 409


def test_extraccion_inexistente_es_404(client: TestClient) -> None:
    assert client.get("/api/extracciones/999999/formulario").status_code == 404


def test_un_dato_no_confirmado_no_queda_buscable(client: TestClient, db: Session) -> None:
    """Criterio de la FASE_3, por las dos vías: semántica y SQL."""
    from app.dominio.facturas import FACTURAS, FiltroFacturas
    from app.services import catalogo

    extraccion_id = _subir(client).json()["extraccion_id"]
    coleccion = catalogo.obtener_coleccion(db, "intereses", "facturas")
    total = FACTURAS.herramienta("total_facturado")
    assert total is not None

    antes = total.ejecutar(db, coleccion.id, FACTURAS.nombre, FiltroFacturas())
    client.post(f"/api/extracciones/{extraccion_id}/confirmacion", json=FACTURA_OLIVOS)
    despues = total.ejecutar(db, coleccion.id, FACTURAS.nombre, FiltroFacturas())

    assert antes.documento_ids == [] and "No hay facturas" in antes.respuesta
    assert len(despues.documento_ids) == 1 and "119.000 CLP" in despues.respuesta


def test_lotes_y_cli_no_saltan_la_confirmacion(client: TestClient, db: Session) -> None:
    from app.common.errors import AppError
    from app.services import catalogo
    from app.services.ingesta import ingestar
    from tests.dobles import proveedor_doble

    coleccion = catalogo.obtener_coleccion(db, "intereses", "facturas")

    with pytest.raises(AppError) as error:
        ingestar(db, coleccion, "f.txt", TEXTO_FACTURA, proveedor_doble(), vision=None)

    assert error.value.status_code == 422
    assert "confirm" in error.value.message
