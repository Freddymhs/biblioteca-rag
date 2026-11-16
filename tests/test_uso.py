"""Tarea 5.2: consultas públicas por día y 429 emitidos, leídos solo con la clave."""

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from redis import Redis

from app.config.constantes import RETENCION_USO_DIAS
from app.config.settings import settings
from main import app

pytestmark = pytest.mark.usefixtures("biblioteca_publica")
PREGUNTA = {"pregunta": "¿Kc del olivo?"}
PRIVADA = {"q": "potasio", "espacio": "personal", "coleccion": "sobre-mi"}


def _hoy() -> str:
    return datetime.now(UTC).date().isoformat()


def test_cuenta_consultas_validas_y_429_por_dia(
    anonimo: TestClient, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LIMITE_RESPUESTAS_POR_MINUTO", 1)
    anonimo.get("/api/publico/buscar", params={"q": "olivo"})
    anonimo.get("/api/publico/buscar", params={"q": "riego"})
    anonimo.get("/api/publico/buscar", params=PRIVADA)  # 404: no es una consulta servida
    anonimo.post("/api/publico/preguntas", json=PREGUNTA)
    anonimo.post("/api/publico/preguntas", json=PREGUNTA)  # 429

    uso = client.get("/api/uso", params={"dias": 1}).json()

    assert uso == [
        {
            "fecha": _hoy(),
            "busquedas": 2,
            "respuestas": 1,
            "rechazos_429": {"busqueda": 0, "respuesta": 1},
        }
    ]


def test_el_mcp_cuenta_igual(url_mcp: str, anonimo: TestClient, client: TestClient) -> None:
    async def buscar() -> Any:
        async with Client(url_mcp) as cliente:
            return await cliente.call_tool("buscar", {"pregunta": "olivo"})

    asyncio.run(buscar())

    assert client.get("/api/uso", params={"dias": 1}).json()[0]["busquedas"] == 1


def test_el_uso_no_es_publico(anonimo: TestClient) -> None:
    assert anonimo.get("/api/uso").status_code == 401
    assert TestClient(app).get("/api/publico/uso").status_code == 404


def test_devuelve_un_dia_por_fila_hasta_el_pedido_y_respeta_la_retencion(
    client: TestClient, anonimo: TestClient, redis_limpio: Redis
) -> None:
    anonimo.get("/api/publico/buscar", params={"q": "olivo"})

    filas = client.get("/api/uso", params={"dias": 3}).json()
    demasiados = client.get("/api/uso", params={"dias": RETENCION_USO_DIAS + 1})
    claves = cast(list[bytes], redis_limpio.keys("uso:*"))
    vidas = [cast(int, redis_limpio.ttl(clave)) for clave in claves]

    assert [fila["busquedas"] for fila in filas] == [1, 0, 0]  # de hoy hacia atrás
    assert demasiados.status_code == 422
    assert claves and all(0 < vida <= RETENCION_USO_DIAS * 24 * 3600 for vida in vidas)
