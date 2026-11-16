"""Embeddings bge-m3 detrás de la interfaz `Embeddings` de LangChain.

Cloudflare se llama por su endpoint compatible con OpenAI (`/ai/v1/embeddings`): es el único de
Workers AI con contrato de respuesta publicado y estable. El nativo `/ai/run/@cf/baai/bge-m3`
documenta `text` en los ejemplos y `contexts` en el esquema, sin esquema de salida síncrona.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import ollama
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from pydantic import SecretStr

from app.common.errors import ErrorProveedor, service_unavailable
from app.config.constantes import (
    CLOUDFLARE_API_BASE,
    DIMENSION_EMBEDDING,
    LOTE_EMBEDDINGS,
    TIMEOUT_EMBEDDINGS_SEGUNDOS,
    AtributoTraza,
    EtapaTraza,
    ProveedorEmbeddings,
)
from app.config.settings import Settings, settings
from app.observabilidad import etapa


class ErrorEmbeddings(ErrorProveedor):
    """El proveedor respondió algo que no es un lote de vectores válido."""


@dataclass(frozen=True)
class ProveedorDeEmbeddings:
    """El cliente y el identificador que se guarda en `trozo.embedding_model`."""

    cliente: Embeddings
    modelo_id: str


class CloudflareEmbeddings(Embeddings):
    def __init__(
        self,
        account_id: str,
        api_token: SecretStr,
        modelo: str,
        cliente_http: httpx.Client | None = None,
    ) -> None:
        self._url = f"{CLOUDFLARE_API_BASE}/{account_id}/ai/v1/embeddings"
        self._api_token = api_token
        self._modelo = modelo
        self._http = cliente_http or httpx.Client(timeout=TIMEOUT_EMBEDDINGS_SEGUNDOS)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectores: list[list[float]] = []
        for inicio in range(0, len(texts), LOTE_EMBEDDINGS):
            vectores.extend(self._embeber_lote(texts[inicio : inicio + LOTE_EMBEDDINGS]))
        return vectores

    def embed_query(self, text: str) -> list[float]:
        return self._embeber_lote([text])[0]

    def _embeber_lote(self, textos: list[str]) -> list[list[float]]:
        respuesta = self._http.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_token.get_secret_value()}"},
            json={"model": self._modelo, "input": textos},
        )
        if respuesta.status_code != httpx.codes.OK:
            raise ErrorEmbeddings(
                f"Cloudflare respondió {respuesta.status_code}: {respuesta.text[:300]}"
            )
        try:
            cuerpo = respuesta.json()
        except ValueError as error:  # JSONDecodeError: un proxy o una página de error HTML
            raise ErrorEmbeddings(
                f"Cloudflare respondió en un formato inesperado: {error}"
            ) from error
        return _vectores_de_respuesta_openai(cuerpo, esperados=len(textos))


# JSON crudo del proveedor (`Any`): su forma se valida en esta misma función.
def _vectores_de_respuesta_openai(cuerpo: Any, esperados: int) -> list[list[float]]:
    """Formato OpenAI: `{"data": [{"index": i, "embedding": [...]}, ...]}`, en cualquier orden."""
    try:
        datos = sorted(cuerpo["data"], key=lambda item: item["index"])
        vectores = [list(item["embedding"]) for item in datos]
    except (KeyError, TypeError, ValueError) as error:
        raise ErrorEmbeddings(
            f"Cloudflare respondió en un formato inesperado: falta o sobra {error!r}"
        ) from error
    if len(vectores) != esperados:
        raise ErrorEmbeddings(f"Se pidieron {esperados} vectores y llegaron {len(vectores)}")
    validar_dimension(vectores)
    return vectores


# Fallas de red o del modelo, no del código: se convierten en ErrorEmbeddings (502).
ERRORES_DE_PROVEEDOR = (httpx.HTTPError, ConnectionError, ollama.ResponseError)


def embeber_documentos(proveedor: ProveedorDeEmbeddings, textos: list[str]) -> list[list[float]]:
    try:
        vectores = proveedor.cliente.embed_documents(textos)
    except ERRORES_DE_PROVEEDOR as error:
        raise ErrorEmbeddings(f"{proveedor.modelo_id} no respondió: {error}") from error
    validar_dimension(vectores)
    return vectores


def embeber_pregunta(proveedor: ProveedorDeEmbeddings, texto: str) -> list[float]:
    try:
        with etapa(EtapaTraza.EMBEBER, {AtributoTraza.PROVEEDOR_EMBEDDINGS: proveedor.modelo_id}):
            vector = proveedor.cliente.embed_query(texto)
    except ERRORES_DE_PROVEEDOR as error:
        raise ErrorEmbeddings(f"{proveedor.modelo_id} no respondió: {error}") from error
    validar_dimension([vector])
    return vector


def validar_dimension(vectores: list[list[float]]) -> None:
    distintos = {len(vector) for vector in vectores} - {DIMENSION_EMBEDDING}
    if distintos:
        raise ErrorEmbeddings(
            f"Dimensión {sorted(distintos)} distinta de la del esquema ({DIMENSION_EMBEDDING})"
        )


def _modelo_id(proveedor: ProveedorEmbeddings, modelo: str) -> str:
    """Lo que se guarda en `trozo.embedding_model`: `proveedor:modelo`."""
    return f"{proveedor.value}:{modelo}"


def crear_proveedor_embeddings(config: Settings) -> ProveedorDeEmbeddings:
    if config.EMBEDDINGS_PROVIDER == ProveedorEmbeddings.OLLAMA:
        cliente = OllamaEmbeddings(
            model=config.OLLAMA_EMBEDDINGS_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            client_kwargs={"timeout": TIMEOUT_EMBEDDINGS_SEGUNDOS},
        )
        return ProveedorDeEmbeddings(
            cliente=cliente,
            modelo_id=_modelo_id(ProveedorEmbeddings.OLLAMA, config.OLLAMA_EMBEDDINGS_MODEL),
        )

    sin_credenciales = (
        not config.CLOUDFLARE_ACCOUNT_ID or not config.CLOUDFLARE_API_TOKEN.get_secret_value()
    )
    if sin_credenciales:
        raise service_unavailable(
            "Embeddings sin configurar: faltan CLOUDFLARE_ACCOUNT_ID y CLOUDFLARE_API_TOKEN "
            "en .env (o usa EMBEDDINGS_PROVIDER=ollama)"
        )
    cliente = CloudflareEmbeddings(
        account_id=config.CLOUDFLARE_ACCOUNT_ID,
        api_token=config.CLOUDFLARE_API_TOKEN,
        modelo=config.CLOUDFLARE_EMBEDDINGS_MODEL,
    )
    return ProveedorDeEmbeddings(
        cliente=cliente,
        modelo_id=_modelo_id(ProveedorEmbeddings.CLOUDFLARE, config.CLOUDFLARE_EMBEDDINGS_MODEL),
    )


@lru_cache(maxsize=1)
def obtener_proveedor_embeddings() -> ProveedorDeEmbeddings:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return crear_proveedor_embeddings(settings)
