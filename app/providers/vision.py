"""Modelo de visión para páginas sin capa de texto, detrás de `BaseChatModel` de LangChain."""

import base64
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from app.config.constantes import (
    MAX_TOKENS_VISION,
    PROMPT_VISION,
    TIMEOUT_VISION_SEGUNDOS,
    EtapaTraza,
    ProveedorVision,
)
from app.config.settings import Settings, settings
from app.providers.llm import TEMPERATURA, invocar


def crear_vision(config: Settings) -> BaseChatModel | None:
    if config.VISION_PROVIDER == ProveedorVision.NINGUNO:
        return None
    return ChatOllama(
        model=config.OLLAMA_VISION_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=TEMPERATURA,
        num_predict=MAX_TOKENS_VISION,
        # Sin esto, un Ollama colgado retiene la página la hora entera del trabajo (medido).
        client_kwargs={"timeout": TIMEOUT_VISION_SEGUNDOS},
    )


def describir_imagen(vision: BaseChatModel, png: bytes) -> str:
    """Lanza `ErrorLLM` si el proveedor falla o responde vacío."""
    url = f"data:image/png;base64,{base64.b64encode(png).decode()}"
    mensaje = HumanMessage(
        content=[
            {"type": "text", "text": PROMPT_VISION},
            {"type": "image_url", "image_url": {"url": url}},
        ]
    )
    return invocar(vision, [mensaje], EtapaTraza.DESCRIBIR_IMAGEN)


@lru_cache(maxsize=1)
def obtener_vision() -> BaseChatModel | None:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return crear_vision(settings)
