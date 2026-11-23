"""Sin IA propia (`LLM_PROVIDER=ninguno`): el MCP solo ofrece `buscar`; redacta el cliente."""

import asyncio

import pytest

from app.common.errors import AppError
from app.config.constantes import ProveedorLLM
from app.config.settings import Settings
from app.mcp_publico import crear_servidor_mcp
from app.providers.llm import MENSAJE_SIN_LLM, crear_llm


def _nombres_de_tools(con_llm: bool) -> list[str]:
    servidor = crear_servidor_mcp({}, con_llm=con_llm)
    return sorted(tool.name for tool in asyncio.run(servidor.list_tools()))


def test_sin_llm_el_mcp_solo_ofrece_buscar() -> None:
    assert _nombres_de_tools(con_llm=False) == ["buscar"]


def test_con_llm_el_mcp_ofrece_buscar_y_preguntar() -> None:
    assert _nombres_de_tools(con_llm=True) == ["buscar", "preguntar"]


def test_las_instrucciones_sin_llm_no_prometen_preguntar() -> None:
    servidor = crear_servidor_mcp({}, con_llm=False)

    assert "preguntar" not in (servidor.instructions or "")


def test_sin_llm_crear_llm_responde_503_con_el_mensaje() -> None:
    with pytest.raises(AppError) as error:
        crear_llm(Settings(LLM_PROVIDER=ProveedorLLM.NINGUNO, DATABASE_URL="sin-base"))

    assert error.value.status_code == 503 and error.value.message == MENSAJE_SIN_LLM
