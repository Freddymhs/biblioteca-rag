"""Puntos de auditorías asignados a la FASE_4: D1 (lo pesado por la cola), F1 (tope de citas de
un cálculo) y F4 (un lote a una colección con paquete se rechaza de entrada)."""

import pytest
from fastapi.testclient import TestClient

from app.config.constantes import TipoDecision
from app.providers.cola import obtener_cola
from app.providers.estructurado import Decision
from app.services import deteccion, enrutamiento
from main import app
from tests.dobles import FACTURA_OLIVOS, ClasificadorDoble, ColaDoble, ExtractorDoble
from tests.pdf_minimo import pdf_minimo

BASE = "/api/espacios/intereses/colecciones"


@pytest.fixture(autouse=True)
def colecciones(client: TestClient) -> None:
    client.post("/api/espacios", json={"slug": "intereses", "nombre": "Intereses"})
    client.post(f"{BASE}", json={"slug": "agricultura", "nombre": "Agricultura"})
    client.post(f"{BASE}", json={"slug": "facturas", "nombre": "F", "paquete": "facturas"})


# ── D1 ───────────────────────────────────────────────────────────────────────


def test_d1_un_pdf_con_muchas_paginas_va_por_la_cola(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deteccion, "MAX_PAGINAS_SUBIDA_SINCRONA", 1)
    archivo = ("largo.pdf", pdf_minimo(["Riego del olivo", "Poda del olivo"]))

    respuesta = client.post(f"{BASE}/agricultura/documentos", files={"archivo": archivo})

    assert respuesta.status_code == 413
    assert "2 páginas" in respuesta.json()["error"] and "lotes" in respuesta.json()["error"]


def test_d1_un_archivo_de_muchos_bytes_va_por_la_cola(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deteccion, "MAX_BYTES_SUBIDA_SINCRONA", 10)
    archivo = ("notas.txt", b"Riego del olivo en verano")

    respuesta = client.post(f"{BASE}/agricultura/documentos", files={"archivo": archivo})

    assert respuesta.status_code == 413


def test_d1_el_lote_acepta_lo_que_la_subida_sincrona_rechaza(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deteccion, "MAX_PAGINAS_SUBIDA_SINCRONA", 1)
    app.dependency_overrides[obtener_cola] = lambda: ColaDoble()
    archivo = ("largo.pdf", pdf_minimo(["Riego del olivo", "Poda del olivo"]))

    respuesta = client.post(f"{BASE}/agricultura/lotes", files={"archivos": archivo})

    assert respuesta.status_code == 202


# ── F4 ───────────────────────────────────────────────────────────────────────


def test_f4_un_lote_a_una_coleccion_con_paquete_es_422_antes_de_tocar_la_cola(
    client: TestClient,
) -> None:
    app.dependency_overrides[obtener_cola] = lambda: ColaDoble(caida=True)  # 503 si la tocara

    respuesta = client.post(
        f"{BASE}/facturas/lotes", files={"archivos": ("f.txt", b"Factura 4521")}
    )

    assert respuesta.status_code == 422
    assert "facturas" in respuesta.json()["error"]


# ── F1 ───────────────────────────────────────────────────────────────────────


def test_f1_un_calculo_cita_a_lo_mas_el_tope_y_dice_cuantos_hay(
    client: TestClient,
    extractor: ExtractorDoble,
    clasificador: ClasificadorDoble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(enrutamiento, "MAX_CITAS_CALCULO", 2)
    for numero in ("1", "2", "3"):
        datos = {**FACTURA_OLIVOS, "numero": numero}
        extractor.datos = datos
        archivo = (f"f{numero}.txt", f"Factura {numero}".encode())
        subida = client.post(f"{BASE}/facturas/documentos", files={"archivo": archivo}).json()
        client.post(f"/api/extracciones/{subida['extraccion_id']}/confirmacion", json=datos)
    clasificador.decision = Decision(tipo=TipoDecision.CALCULO, herramienta="total_facturado")

    cuerpo = client.post(
        "/api/preguntas",
        json={"pregunta": "¿Cuánto?", "espacio": "intereses", "coleccion": "facturas"},
    ).json()

    assert len(cuerpo["citas"]) == 2
    assert "en 3 facturas" in cuerpo["respuesta"] and "Se citan 2 de 3" in cuerpo["respuesta"]
