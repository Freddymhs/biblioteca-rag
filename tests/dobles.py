"""Dobles de proveedores. Los embeddings son un «bolsa de palabras» sobre un vocabulario fijo:
textos que comparten palabras quedan cerca por coseno, y uno sin palabras conocidas queda lejos."""

import math
import re
from typing import Any, Protocol

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.common.errors import service_unavailable
from app.config.constantes import DIMENSION_EMBEDDING
from app.providers.embeddings import ProveedorDeEmbeddings

VOCABULARIO = [
    "olivo", "riego", "kc", "poda", "maracuya", "pitahaya", "fertilizacion", "potasio",
    "cosecha", "tuna", "cochinilla", "arandano",
]  # fmt: skip
DIMENSION_RESTO = DIMENSION_EMBEDDING - 1  # todo texto suma algo aquí: nunca hay vector nulo
PESO_RESTO = 0.05
MODELO_DOBLE = "doble:bolsa-de-palabras"
# Contiene «potasio» y «cosecha» del vocabulario: el doble de embeddings la encuentra.
DESCRIPCION_VISION = "Grafico de potasio absorbido durante la cosecha"


class EmbeddingsPorPalabras(Embeddings):
    def __init__(self) -> None:
        self.llamadas = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.llamadas += 1
        return [self._vector(texto) for texto in texts]

    def embed_query(self, text: str) -> list[float]:
        self.llamadas += 1
        return self._vector(text)

    @staticmethod
    def _vector(texto: str) -> list[float]:
        palabras = set(re.findall(r"[a-záéíóúñ]+", texto.lower()))
        vector = [1.0 if termino in palabras else 0.0 for termino in VOCABULARIO]
        vector += [0.0] * (DIMENSION_EMBEDDING - len(VOCABULARIO))
        vector[DIMENSION_RESTO] = PESO_RESTO
        norma = math.sqrt(sum(componente * componente for componente in vector))
        return [componente / norma for componente in vector]


class EmbeddingsCaidos(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("conexión rechazada")

    def embed_query(self, text: str) -> list[float]:
        raise ConnectionError("conexión rechazada")


def proveedor_doble(cliente: Embeddings | None = None, modelo_id: str = MODELO_DOBLE):
    return ProveedorDeEmbeddings(cliente=cliente or EmbeddingsPorPalabras(), modelo_id=modelo_id)


class LLMGrabador(BaseChatModel):
    """Responde siempre lo mismo y guarda cada conversación que recibe."""

    respuesta: str = "El Kc del olivo es 0.65 [1]."
    recibidos: list[list[BaseMessage]] = Field(default_factory=list)
    falla: bool = False

    @property
    def _llm_type(self) -> str:
        return "grabador"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,  # firma de BaseChatModel: argumentos libres del proveedor
    ) -> ChatResult:
        self.recibidos.append(messages)
        if self.falla:
            raise ConnectionError("conexión rechazada")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(self.respuesta))])


class ColaDoble:
    def __init__(self, caida: bool = False) -> None:
        self.encolados: list[tuple[str, tuple[Any, ...]]] = []
        self.ids_de_tarea: list[str] = []
        self.verificaciones = 0
        self.caida = caida

    async def verificar(self) -> None:
        self.verificaciones += 1
        if self.caida:
            raise service_unavailable("La cola de trabajos (Redis) no responde")

    async def encolar(self, funcion: str, *argumentos: Any, id_tarea: str) -> None:
        if self.caida:
            raise service_unavailable("La cola de trabajos (Redis) no responde")
        self.encolados.append((funcion, argumentos))
        self.ids_de_tarea.append(id_tarea)


class RespuestaHTTP(Protocol):
    """Lo que los tests leen de una respuesta de `TestClient`. Estructural: Starlette usa `httpx2`
    si está instalado (lo trae `anthropic`) o `httpx`, y este tipo sirve con los dos."""

    status_code: int

    # `Any`: el cuerpo JSON de la API, que cada test valida con sus asserts.
    def json(self) -> Any: ...


# Factura válida según `app.dominio.facturas.Factura` (montos como texto: JSON de Pydantic).
FACTURA_OLIVOS = {
    "numero": "4521",
    "fecha": "2026-03-12",
    "emisor": "Agricola Los Olivos SpA",
    "rut_emisor": None,
    "receptor": None,
    "moneda": "CLP",
    "neto": "100000",
    "iva": "19000",
    "total": "119000",
    "lineas": [],
}


class ExtractorDoble:
    """Devuelve siempre la misma propuesta y guarda los textos que recibió."""

    def __init__(
        self, datos: dict[str, Any] | None = None, errores: list[str] | None = None
    ) -> None:
        self.datos = dict(FACTURA_OLIVOS) if datos is None else datos
        self.errores = errores or []
        self.textos: list[str] = []

    def __call__(self, esquema: type, texto: str) -> Any:
        from app.providers.estructurado import Propuesta

        self.textos.append(texto)
        return Propuesta(dict(self.datos), list(self.errores))


class ClasificadorDoble:
    def __init__(self, decision: Any = None) -> None:
        from app.providers.estructurado import SIGNIFICADO

        self.decision = decision or SIGNIFICADO
        self.preguntas: list[str] = []

    def __call__(self, pregunta: str, paquete: Any, hoy: Any) -> Any:
        self.preguntas.append(pregunta)
        return self.decision


# Biblioteca de la API pública y el MCP (FASE_4): (espacio, colección, pública, archivo, texto,
# licencia verificada). Solo olivo.txt es público: poda no tiene licencia verificada y
# potasio está en una colección privada, aunque los tres hablan del olivo.
LICENCIA_DOBLE = "CC BY 4.0"
BIBLIOTECA_PUBLICA = [
    ("intereses", "agricultura", True, "olivo.txt", "El Kc del olivo es 0.65 en riego.", True),
    ("intereses", "agricultura", True, "poda.txt", "Poda del olivo en invierno.", False),
    ("personal", "sobre-mi", False, "potasio.txt", "Fertilizacion con potasio en el olivo.", True),
]
