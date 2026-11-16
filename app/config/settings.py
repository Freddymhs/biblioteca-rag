from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.constantes import ProveedorEmbeddings, ProveedorLLM, ProveedorVision


class Settings(BaseSettings):
    """
    Variables de entorno validadas al arrancar: si falta una obligatoria, la app no levanta.
    Lee `.env` automáticamente. Las claves de proveedores son opcionales: la API arranca
    sin ellas y los endpoints que las necesitan responden 503 hasta que se configuren.
    """

    # Obligatorias
    DATABASE_URL: str
    SECRET_KEY: str

    # Opcionales con valor por defecto
    APP_NAME: str = "biblioteca-rag"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = []  # vacía = ningún origen cruzado. Ej. ["https://app.example.com"]

    # Embeddings
    EMBEDDINGS_PROVIDER: ProveedorEmbeddings = ProveedorEmbeddings.CLOUDFLARE
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: SecretStr = SecretStr("")
    CLOUDFLARE_EMBEDDINGS_MODEL: str = "@cf/baai/bge-m3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDINGS_MODEL: str = "bge-m3"

    # LLM. `ollama` existe para probar de punta a punta sin gastar la cuota de MiniMax.
    LLM_PROVIDER: ProveedorLLM = ProveedorLLM.MINIMAX
    OLLAMA_LLM_MODEL: str = "llama3.2:3b"
    MINIMAX_API_KEY: SecretStr = SecretStr("")
    MINIMAX_BASE_URL: str = "https://api.minimax.io/anthropic"
    MINIMAX_MODEL: str = "MiniMax-M2.7-highspeed"

    # Visión para páginas sin texto. `ninguno` las deja sin indexar (solo se registran).
    VISION_PROVIDER: ProveedorVision = ProveedorVision.OLLAMA
    OLLAMA_VISION_MODEL: str = "moondream"

    # Conectores. Vacío = desactivado (el endpoint de sincronización responde 503).
    RESUME_API_URL: str = ""

    # Ingesta en segundo plano. La carpeta la comparten la API (escribe) y el worker (lee).
    REDIS_URL: str = "redis://localhost:6379"
    INGESTA_TEMPORAL: Path = Path("/tmp/biblioteca-rag/ingesta")

    # Pregunta: distancia coseno máxima para que un trozo cuente como relevante.
    # Calibrado el 2026-11-16 con bge-m3 (Ollama) y las preguntas de oro sobre 6 documentos:
    # trozos correctos entre 0,24 y 0,51; sin respuesta desde 0,61.
    # Recalibrar con el corpus completo.
    PREGUNTA_DISTANCIA_MAXIMA: float = 0.55

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Singleton — importar este en vez de instanciar de nuevo
settings = Settings()  # type: ignore[call-arg]
