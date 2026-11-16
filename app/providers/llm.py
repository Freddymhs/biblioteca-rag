"""LLM que redacta la respuesta, detrás de `BaseChatModel` de LangChain. Temperatura 0."""

from collections.abc import Sequence
from functools import lru_cache

import anthropic
import httpx
import ollama
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama

from app.common.errors import ErrorProveedor, service_unavailable
from app.config.constantes import MAX_TOKENS_RESPUESTA, TIMEOUT_LLM_SEGUNDOS, ProveedorLLM
from app.config.settings import Settings, settings

TEMPERATURA = 0.0
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
    try:
        respuesta = llm.invoke(mensajes)
    except ERRORES_DE_PROVEEDOR as error:
        raise ErrorLLM(f"El LLM no respondió: {error}") from error
    texto = respuesta.text.strip()
    if not texto:
        # Sin texto no hay respuesta que mostrar ni citas que respaldar: es una falla del proveedor.
        raise ErrorLLM("El LLM devolvió una respuesta vacía")
    return texto


@lru_cache(maxsize=1)
def obtener_llm() -> BaseChatModel:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return crear_llm(settings)
