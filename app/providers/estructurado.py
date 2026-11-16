"""Salida estructurada del LLM: extraer datos de un documento y clasificar una pregunta.

Ambas son funciones inyectables (dependencias de FastAPI): los tests las reemplazan por dobles y
el resto del código no sabe qué LLM hay detrás. Medido el 2026-11-16 con Ollama `llama3.2:3b`:
`method="json_schema"` funciona; `function_calling` falla en las fechas.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, create_model

from app.common.logger import logger
from app.config.constantes import MAX_CARACTERES_EXTRACCION, TipoDecision
from app.dominio.base import PaqueteDominio
from app.providers.llm import ERRORES_DE_PROVEEDOR, obtener_llm

INSTRUCCIONES_EXTRACCION = """Extrae los datos del documento según el esquema.
- Copia los valores tal como aparecen; no inventes datos que no estén.
- Fechas en formato AAAA-MM-DD (ojo: «12-03-2026» es día 12, mes 03, año 2026).
- Montos como números sin separadores de miles.
- Moneda como código ISO 4217 (CLP, USD…); si el documento no la dice, déjala vacía."""

INSTRUCCIONES_CLASIFICACION = """Clasifica la pregunta sobre una colección de {descripcion}
- «calculo»: pide un número que se obtiene sumando, contando o comparando datos (totales,
  cantidades, rankings, el mayor). Elige UNA herramienta de la lista y sus argumentos.
- «significado»: pide explicar, describir o encontrar algo en el texto de los documentos.
Hoy es {hoy}. Herramientas (nombre: descripción · argumentos en JSON Schema):
{herramientas}"""


@dataclass(frozen=True)
class Propuesta:
    # `Any`: JSON con la forma del esquema del paquete (puede no validar: ver `errores`).
    datos: dict[str, Any]
    errores: list[str]


class Decision(BaseModel):
    """Lo que devuelve el clasificador. No hay campo para SQL: solo nombre de herramienta y
    argumentos, que después valida el modelo Pydantic de esa herramienta."""

    tipo: TipoDecision
    herramienta: str | None = None
    # `Any`: argumentos propuestos por el LLM; se validan contra la herramienta elegida.
    argumentos: dict[str, Any] = Field(default_factory=dict)


Extractor = Callable[[type[BaseModel], str], Propuesta]
Clasificador = Callable[[str, PaqueteDominio, date], Decision]
SIGNIFICADO = Decision(tipo=TipoDecision.SIGNIFICADO)


def extraer_con_llm(llm: BaseChatModel) -> Extractor:
    def extraer(esquema: type[BaseModel], texto: str) -> Propuesta:
        estructurado = llm.with_structured_output(esquema, method="json_schema", include_raw=True)
        mensajes = [
            SystemMessage(INSTRUCCIONES_EXTRACCION),
            HumanMessage(texto[:MAX_CARACTERES_EXTRACCION]),
        ]
        try:
            salida = estructurado.invoke(mensajes)
        except ERRORES_DE_PROVEEDOR as error:
            # Sin propuesta igual se crea la extracción: una persona la completa en el formulario.
            logger.warning(f"Extracción sin propuesta: el LLM no respondió ({error})")
            return Propuesta({}, [f"el LLM no respondió: {error}"])
        return _propuesta(esquema, salida)

    return extraer


# `Any`: la salida de `with_structured_output(include_raw=True)` es un dict de LangChain.
def _propuesta(esquema: type[BaseModel], salida: Any) -> Propuesta:
    parseado = salida.get("parsed")
    if isinstance(parseado, BaseModel):
        return Propuesta(parseado.model_dump(mode="json"), [])
    crudo = getattr(salida.get("raw"), "text", "") or ""
    try:
        datos = json.loads(crudo)
    except ValueError:
        return Propuesta({}, [f"el LLM no devolvió JSON: {crudo[:200]!r}"])
    if not isinstance(datos, dict):
        return Propuesta({}, ["el LLM no devolvió un objeto JSON"])
    try:
        esquema.model_validate(datos)
    except ValidationError as error:
        return Propuesta(datos, _errores(error))
    return Propuesta(datos, [])


def _errores(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(parte) for parte in detalle['loc'])}: {detalle['msg']}"
        for detalle in error.errors()
    ]


def esquema_de_decision(paquete: PaqueteDominio) -> type[BaseModel]:
    """El esquema que ve el LLM: `herramienta` obligatoria y restringida a las del paquete.

    Medido el 2026-11-16 con llama3.2:3b: con `herramienta` opcional, respondía «calculo» y la
    omitía. Con `json_schema`, Ollama restringe la decodificación a este enum: no puede inventar
    una herramienta ni saltársela."""
    nombres = tuple(herramienta.nombre for herramienta in paquete.herramientas)
    # `Any` en argumentos: los valida después el modelo Pydantic de la herramienta elegida.
    return create_model(
        "DecisionPaquete",
        tipo=(TipoDecision, ...),
        herramienta=(Literal[nombres] | None, ...),  # type: ignore[valid-type]  # enum dinámico
        argumentos=(dict[str, Any], ...),
    )


def clasificar_con_llm(llm: BaseChatModel) -> Clasificador:
    def clasificar(pregunta: str, paquete: PaqueteDominio, hoy: date) -> Decision:
        herramientas = "\n".join(
            f"- {h.nombre}: {h.descripcion} · {json.dumps(h.argumentos.model_json_schema())}"
            for h in paquete.herramientas
        )
        sistema = INSTRUCCIONES_CLASIFICACION.format(
            descripcion=paquete.descripcion, hoy=hoy.isoformat(), herramientas=herramientas
        )
        esquema = esquema_de_decision(paquete)
        try:
            salida = llm.with_structured_output(esquema, method="json_schema").invoke(
                [SystemMessage(sistema), HumanMessage(pregunta)]
            )
            # Primero contra el esquema estricto del paquete (herramienta obligatoria, enum
            # cerrado): un proveedor que devuelva un dict incompleto no pasa como cálculo.
            estricta = salida if isinstance(salida, esquema) else esquema.model_validate(salida)
            return Decision.model_validate(estricta.model_dump())
        except (*ERRORES_DE_PROVEEDOR, ValidationError, ValueError) as error:
            # Ante la duda, búsqueda semántica: nunca un cálculo que nadie pidió.
            logger.warning(f"Clasificación fallida, se busca por significado: {error!r}")
            return SIGNIFICADO

    return clasificar


@lru_cache(maxsize=1)
def obtener_extractor() -> Extractor:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return extraer_con_llm(obtener_llm())


def obtener_fabrica_extractor() -> Callable[[], Extractor]:
    """Dependencia de FastAPI: entrega la FÁBRICA, no el extractor. Instanciarlo crea el LLM, y
    una subida a una colección sin paquete no debe exigir un LLM configurado."""
    return obtener_extractor


@lru_cache(maxsize=1)
def obtener_clasificador() -> Clasificador:
    return clasificar_con_llm(obtener_llm())
