"""Dobles de proveedores. Los embeddings son un «bolsa de palabras» sobre un vocabulario fijo:
textos que comparten palabras quedan cerca por coseno, y uno sin palabras conocidas queda lejos."""

import math
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.config.constantes import DIMENSION_EMBEDDING
from app.providers.embeddings import ProveedorDeEmbeddings

VOCABULARIO = [
    "olivo", "riego", "kc", "poda", "maracuya", "pitahaya", "fertilizacion", "potasio",
    "cosecha", "tuna", "cochinilla", "arandano",
]  # fmt: skip
DIMENSION_RESTO = DIMENSION_EMBEDDING - 1  # todo texto suma algo aquí: nunca hay vector nulo
PESO_RESTO = 0.05
MODELO_DOBLE = "doble:bolsa-de-palabras"


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
