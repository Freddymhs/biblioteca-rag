"""Tarea 4.5: sin API key no se escribe ni se lee lo privado; la clave sale de .env."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config.constantes import ENCABEZADO_API_KEY
from app.config.settings import settings
from main import app

ESPACIO = {"slug": "laboral", "nombre": "Laboral"}
PUBLICAS = {"/health"}
PREFIJO_PUBLICO = "/api/publico"
# Una por router privado: escribir y leer.
RUTAS_PRIVADAS = [
    ("POST", "/api/espacios"),
    ("GET", "/api/espacios"),
    ("PATCH", "/api/espacios/laboral/colecciones/agricultura"),
    ("POST", "/api/espacios/laboral/colecciones/agricultura/documentos"),
    ("PUT", "/api/espacios/laboral/colecciones/agricultura/documentos/1/licencia"),
    ("POST", "/api/espacios/laboral/colecciones/agricultura/lotes"),
    ("GET", "/api/trabajos/1"),
    ("POST", "/api/preguntas"),
    ("GET", "/api/extracciones/1/formulario"),
]


@pytest.fixture
def anonimo(client: TestClient) -> TestClient:
    """El mismo cliente (base y dobles) pero sin el encabezado de la clave."""
    return TestClient(app)


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_PRIVADAS)
def test_sin_api_key_todo_lo_privado_es_401(anonimo: TestClient, metodo: str, ruta: str) -> None:
    respuesta = anonimo.request(metodo, ruta, json=ESPACIO)

    assert respuesta.status_code == 401
    assert ENCABEZADO_API_KEY in respuesta.json()["error"]


def test_con_otra_clave_es_401(anonimo: TestClient) -> None:
    respuesta = anonimo.post("/api/espacios", json=ESPACIO, headers={ENCABEZADO_API_KEY: "otra"})

    assert respuesta.status_code == 401


def test_con_la_clave_escribe(client: TestClient) -> None:
    assert client.post("/api/espacios", json=ESPACIO).status_code == 201


def test_sin_clave_configurada_lo_privado_queda_cerrado(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "API_KEY", SecretStr(""))

    respuesta = client.post("/api/espacios", json=ESPACIO)

    assert respuesta.status_code == 503


def test_salud_y_documentacion_no_piden_clave(anonimo: TestClient) -> None:
    assert anonimo.get("/health").status_code == 200
    assert anonimo.get("/openapi.json").status_code == 200


def test_cada_operacion_es_publica_o_exige_la_clave(anonimo: TestClient) -> None:
    """Una ruta nueva olvidada fuera del grupo privado aparece aquí (lo dice el OpenAPI)."""
    operaciones = anonimo.get("/openapi.json").json()["paths"]
    sin_clave = [
        f"{metodo.upper()} {camino}"
        for camino, metodos in operaciones.items()
        for metodo, operacion in metodos.items()
        if not operacion.get("security")
        and camino not in PUBLICAS
        and not camino.startswith(PREFIJO_PUBLICO)
    ]

    assert len(operaciones) > len(RUTAS_PRIVADAS)  # denominador: el barrido vio rutas
    assert sin_clave == []
