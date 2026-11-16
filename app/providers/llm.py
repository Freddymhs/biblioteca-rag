"""LLM que redacta la respuesta, detrás de `BaseChatModel` de LangChain. Temperatura 0."""

from collections.abc import Sequence
from functools import lru_cache

import anthropic
import httpx
import langsmith
import ollama
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama

from app.common.errors import ErrorProveedor, service_unavailable
from app.config.constantes import (
    MAX_TOKENS_RESPUESTA,
    TIMEOUT_LLM_SEGUNDOS,
    AtributoTraza,
    EtapaTraza,
    ProveedorLLM,
)
from app.config.settings import Settings, settings
from app.observabilidad import etapa

TEMPERATURA = 0.0

# I11: LangSmith viene con LangChain y, encendido por entorno (LANGSMITH_TRACING), mandaría los
# prompts (con la pregunta) a un servicio externo. Se apaga por construcción al cargar este
# módulo, que importan la API y el worker: el interruptor global le gana al entorno.
langsmith.configure(enabled=False)
ERRORES_DE_PROVEEDOR = (anthropic.APIError, ollama.ResponseError, httpx.HTTPError, ConnectionError)


class ErrorLLM(ErrorProveedor):
    pass


def crear_llm(config: Settings) -> BaseChatModel:
    if config.LLM_PROVIDER == ProveedorLLM.OLLAMA:
        return ChatOllama(
            model=config.OLLAMA_LLM_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=TEMPERATURA,
            num_predict=MAX_TOKENS_RESPUESTA,
            reasoning=False,  # pide solo la respuesta final a modelos con «thinking»
            client_kwargs={"timeout": TIMEOUT_LLM_SEGUNDOS},
        )

    if not config.MINIMAX_API_KEY.get_secret_value():
        raise service_unavailable(
            "LLM sin configurar: falta MINIMAX_API_KEY en .env (o usa LLM_PROVIDER=ollama)"
        )
    return ChatAnthropic(
        model_name=config.MINIMAX_MODEL,
        base_url=config.MINIMAX_BASE_URL,
        api_key=config.MINIMAX_API_KEY,
        temperature=TEMPERATURA,
        max_tokens_to_sample=MAX_TOKENS_RESPUESTA,
        timeout=TIMEOUT_LLM_SEGUNDOS,
        stop=None,  # explícito: pyright no ve el default detrás del alias `stop_sequences`
    )


def redactar(llm: BaseChatModel, mensajes: Sequence[BaseMessage]) -> str:
    return invocar(llm, mensajes, EtapaTraza.REDACTAR)


def invocar(llm: BaseChatModel, mensajes: Sequence[BaseMessage], etapa_traza: EtapaTraza) -> str:
    """Llama al modelo con su etapa en la traza (redactar, describir una imagen…)."""
    try:
        with etapa(etapa_traza, {AtributoTraza.PROVEEDOR_LLM: nombre_del_llm(llm)}):
            respuesta = llm.invoke(mensajes)
    except ERRORES_DE_PROVEEDOR as error:
        raise ErrorLLM(f"El LLM no respondió: {error}") from error
    texto = respuesta.text.strip()
    if not texto:
        # Sin texto no hay respuesta que mostrar ni citas que respaldar: es una falla del proveedor.
        raise ErrorLLM("El LLM devolvió una respuesta vacía")
    return texto


def nombre_del_llm(llm: BaseChatModel) -> str:
    """Clase y modelo (ej. «ChatOllama:llama3.2:3b»), para la traza."""
    modelo = getattr(llm, "model", None) or getattr(llm, "model_name", None) or ""
    return f"{type(llm).__name__}:{modelo}" if modelo else type(llm).__name__


@lru_cache(maxsize=1)
def obtener_llm() -> BaseChatModel:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return crear_llm(settings)
