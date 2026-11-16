"""Auditoría FASE_3 E11: extractor y clasificador reales contra salidas simuladas del LLM."""

from datetime import date
from typing import Any, cast

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.config.constantes import TipoDecision
from app.dominio import obtener_paquete
from app.dominio.facturas import Factura
from app.providers.estructurado import SIGNIFICADO, clasificar_con_llm, extraer_con_llm
from tests.dobles import FACTURA_OLIVOS

HOY = date(2026, 11, 16)


class LLMEstructuradoDoble:
    """Imita `llm.with_structured_output(...).invoke(...)`: devuelve `salida` o lanza `error`."""

    def __init__(self, salida: Any = None, error: Exception | None = None) -> None:
        self.salida = salida
        self.error = error
        self.esquemas: list[Any] = []

    def with_structured_output(self, esquema: Any, **_opciones: Any) -> "LLMEstructuradoDoble":
        self.esquemas.append(esquema)
        return self

    def invoke(self, _mensajes: Any) -> Any:
        if self.error is not None:
            raise self.error
        return self.salida


def _como_llm(doble: LLMEstructuradoDoble) -> BaseChatModel:
    return cast(BaseChatModel, doble)


def _crudo(contenido: str) -> dict[str, Any]:
    return {"raw": AIMessage(contenido), "parsed": None, "parsing_error": ValueError("x")}


# ── extractor ─────────────────────────────────────────────────────────────────


def test_extractor_con_salida_valida_devuelve_los_datos_sin_errores() -> None:
    parseado = Factura.model_validate(FACTURA_OLIVOS)
    doble = LLMEstructuradoDoble({"raw": AIMessage(""), "parsed": parseado, "parsing_error": None})

    propuesta = extraer_con_llm(_como_llm(doble))(Factura, "texto")

    assert (propuesta.datos["numero"], propuesta.errores) == ("4521", [])


@pytest.mark.parametrize(
    ("contenido", "motivo"),
    [("{no es json", "no devolvió JSON"), ('["lista"]', "no devolvió un objeto")],
    ids=["json-roto", "no-objeto"],
)
def test_extractor_con_salida_ilegible_deja_la_propuesta_vacia(contenido: str, motivo: str) -> None:
    propuesta = extraer_con_llm(_como_llm(LLMEstructuradoDoble(_crudo(contenido))))(Factura, "t")

    assert propuesta.datos == {}
    assert motivo in propuesta.errores[0]


def test_extractor_conserva_una_propuesta_que_no_valida_con_sus_errores() -> None:
    contenido = '{"numero": "4521", "fecha": "1203-03-26", "emisor": "X", "total": "1"}'

    propuesta = extraer_con_llm(_como_llm(LLMEstructuradoDoble(_crudo(contenido))))(Factura, "t")

    assert propuesta.datos["fecha"] == "1203-03-26"  # se muestra para corregir, no se pierde
    assert any("fecha" in error for error in propuesta.errores)
    assert any("moneda" in error for error in propuesta.errores)  # la moneda no se supone


def test_extractor_con_llm_caido_crea_la_extraccion_igual() -> None:
    caido = LLMEstructuradoDoble(error=httpx.ConnectError("sin conexión"))

    propuesta = extraer_con_llm(_como_llm(caido))(Factura, "t")

    assert propuesta.datos == {}
    assert "no respondió" in propuesta.errores[0]


# ── clasificador ──────────────────────────────────────────────────────────────


def test_clasificador_convierte_la_salida_en_una_decision() -> None:
    paquete = obtener_paquete("facturas")
    salida = {"tipo": "calculo", "herramienta": "total_facturado", "argumentos": {}}
    doble = LLMEstructuradoDoble(salida)

    decision = clasificar_con_llm(_como_llm(doble))("¿Cuánto?", paquete, HOY)

    assert (decision.tipo, decision.herramienta) == (TipoDecision.CALCULO, "total_facturado")
    assert doble.esquemas[0].__name__ == "DecisionPaquete"  # el esquema con enum cerrado


@pytest.mark.parametrize(
    "doble",
    [
        LLMEstructuradoDoble(error=httpx.ConnectError("sin conexión")),
        LLMEstructuradoDoble({"tipo": "borrar", "herramienta": None, "argumentos": {}}),
        LLMEstructuradoDoble({"tipo": "calculo"}),  # sin herramienta ni argumentos
    ],
    ids=["llm-caido", "tipo-inexistente", "incompleta"],
)
def test_clasificador_ante_cualquier_falla_va_por_significado(doble: LLMEstructuradoDoble) -> None:
    decision = clasificar_con_llm(_como_llm(doble))("¿Cuánto?", obtener_paquete("facturas"), HOY)

    assert decision == SIGNIFICADO
