"""Tarea 4.7: un agente externo consulta por MCP (HTTP) y recibe fragmentos con cita.

Servidor real (uvicorn en un hilo) y el cliente oficial del SDK: el mismo camino que haría
Hermes. Los datos y las sustituciones son los de la API pública (`biblioteca_publica`, `anonimo`).
"""

import asyncio
from typing import Any

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.config.constantes import ENCABEZADO_IP_CLOUDFLARE
from app.config.settings import settings
from tests.dobles import LICENCIA_DOBLE, LLMGrabador

ESPERA_ARRANQUE_SEGUNDOS = 10.0
pytestmark = pytest.mark.usefixtures("biblioteca_publica")
INTERVALO_SONDEO_SEGUNDOS = 0.05


# `Any`: argumentos JSON de la tool y su resultado del SDK.
def _llamar(url: str, tool: str, argumentos: dict[str, Any]) -> Any:
    async def llamar() -> Any:
        async with Client(url) as cliente:
            return await cliente.call_tool(tool, argumentos)

    return asyncio.run(llamar())


def _tools(url: str) -> Any:
    async def listar() -> Any:
        async with Client(url) as cliente:
            return (await cliente.list_tools()).tools

    return asyncio.run(listar())


def test_expone_solo_buscar_y_preguntar_de_solo_lectura(url_mcp: str) -> None:
    tools = _tools(url_mcp)

    assert sorted(tool.name for tool in tools) == ["buscar", "preguntar"]
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools)


def test_buscar_devuelve_fragmentos_con_cita_solo_de_lo_publico(
    url_mcp: str, anonimo: TestClient, llm: LLMGrabador
) -> None:
    resultado = _llamar(url_mcp, "buscar", {"pregunta": "riego del olivo"})

    fragmentos = resultado.structured_content["fragmentos"]
    assert not resultado.is_error
    assert {f["documento"] for f in fragmentos} == {"olivo.txt"}  # ni poda ni potasio
    assert fragmentos[0]["licencia"] == LICENCIA_DOBLE and "0.65" in fragmentos[0]["fragmento"]
    assert llm.recibidos == []  # buscar no usa el LLM


def test_preguntar_redacta_con_cita(url_mcp: str, anonimo: TestClient, llm: LLMGrabador) -> None:
    resultado = _llamar(url_mcp, "preguntar", {"pregunta": "¿Kc del olivo?"})

    cuerpo = resultado.structured_content
    assert (cuerpo["sabe"], [c["documento"] for c in cuerpo["citas"]]) == (True, ["olivo.txt"])


def test_una_coleccion_privada_no_existe_por_mcp(url_mcp: str, anonimo: TestClient) -> None:
    argumentos = {"pregunta": "potasio", "espacio": "personal", "coleccion": "sobre-mi"}

    resultado = _llamar(url_mcp, "buscar", argumentos)

    assert resultado.is_error
    assert "no existe" in resultado.content[0].text


def test_el_mcp_comparte_el_limite_por_ip(
    url_mcp: str, anonimo: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LIMITE_BUSQUEDAS_POR_MINUTO", 1)

    primera = _llamar(url_mcp, "buscar", {"pregunta": "olivo"})
    segunda = _llamar(url_mcp, "buscar", {"pregunta": "olivo"})

    assert (primera.is_error, segunda.is_error) == (False, True)
    assert "Límite" in segunda.content[0].text


def test_un_host_desconocido_se_rechaza(url_mcp: str) -> None:
    """Protección del SDK contra DNS rebinding: solo los hosts de MCP_HOSTS_PERMITIDOS."""
    import httpx

    respuesta = httpx.post(url_mcp, json={}, headers={"Host": "atacante.example"})

    assert respuesta.status_code in (400, 421)


def test_coleccion_sin_espacio_es_un_error_claro(url_mcp: str, anonimo: TestClient) -> None:
    resultado = _llamar(url_mcp, "buscar", {"pregunta": "olivo", "coleccion": "agricultura"})

    assert resultado.is_error and "422: una colección se nombra" in resultado.content[0].text


# ── G12: el límite del MCP es por IP de verdad y compartido con REST ─────────


def _buscar_desde(url: str, ip: str) -> Any:
    async def llamar() -> Any:
        cliente_http = httpx2.AsyncClient(headers={ENCABEZADO_IP_CLOUDFLARE: ip})
        async with cliente_http, Client(streamable_http_client(url, http_client=cliente_http)) as c:
            return await c.call_tool("buscar", {"pregunta": "olivo"})

    return asyncio.run(llamar())


def test_g12_el_mcp_cuenta_por_la_ip_del_visitante(
    url_mcp: str, anonimo: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falla si la IP fuera siempre «desconocida»: la segunda IP no compartiría el contador."""
    monkeypatch.setattr(settings, "LIMITE_BUSQUEDAS_POR_MINUTO", 1)
    monkeypatch.setattr(settings, "CONFIAR_EN_CF_CONNECTING_IP", True)

    errores = [_buscar_desde(url_mcp, ip).is_error for ip in ("1.1.1.1", "2.2.2.2", "1.1.1.1")]

    assert errores == [False, False, True]


def test_g12_rest_y_mcp_comparten_el_contador(
    url_servidor: str, url_mcp: str, anonimo: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LIMITE_BUSQUEDAS_POR_MINUTO", 1)
    monkeypatch.setattr(settings, "CONFIAR_EN_CF_CONNECTING_IP", True)

    rest = httpx.get(
        f"{url_servidor}/api/publico/buscar",
        params={"q": "olivo"},
        headers={ENCABEZADO_IP_CLOUDFLARE: "3.3.3.3"},
    )
    mcp = _buscar_desde(url_mcp, "3.3.3.3")

    assert rest.status_code == 200
    assert mcp.is_error and "Límite" in mcp.content[0].text
