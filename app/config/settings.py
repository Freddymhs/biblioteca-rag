from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.constantes import (
    MIN_LARGO_API_KEY,
    ProveedorEmbeddings,
    ProveedorLLM,
    ProveedorVision,
)


class Settings(BaseSettings):
    """
    Variables de entorno validadas al arrancar: si falta una obligatoria, la app no levanta.
    Lee `.env` automáticamente. Las claves de proveedores son opcionales: la API arranca
    sin ellas y los endpoints que las necesitan responden 503 hasta que se configuren.
    """

    # Obligatorias
    DATABASE_URL: str

    # Servicio público (FASE_4). Sin API_KEY no se escribe ni se lee lo privado (503: fail-closed).
    API_KEY: SecretStr = SecretStr("")
    # Conexión de la API pública y el MCP: el usuario con login del grupo `biblioteca_publico`
    # (crearlo con `python -m app.cli.usuario_publico`). Vacía: la API no arranca (G6), salvo
    # PERMITIR_PUBLICO_SIN_USUARIO=true (solo desarrollo: conexión del dueño con role=, deshacible).
    DATABASE_URL_PUBLICA: SecretStr = SecretStr("")
    PERMITIR_PUBLICO_SIN_USUARIO: bool = False

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
    # Con contraseña (D6): redis://:<REDIS_PASSWORD>@host:6379
    REDIS_URL: str = "redis://localhost:6379"
    INGESTA_TEMPORAL: Path = Path("/tmp/biblioteca-rag/ingesta")

    # Pregunta: distancia coseno máxima para que un trozo cuente como relevante.
    # Calibrado el 2026-11-16 con bge-m3 (Ollama) y las preguntas de oro sobre 6 documentos:
    # trozos correctos entre 0,24 y 0,51; sin respuesta desde 0,61.
    # Recalibrar con el corpus completo.
    PREGUNTA_DISTANCIA_MAXIMA: float = 0.55

    # Límites de la API pública y el MCP (tarea 4.4). Superarlos responde 429.
    # Por minuto y por IP: se cuenta toda petición (barato). Las cuotas diarias se cuentan solo
    # después de validar (un 404 o 422 no las gasta). IPv6 se agrupa por /64 (G3).
    LIMITE_BUSQUEDAS_POR_MINUTO: int = 30
    LIMITE_RESPUESTAS_POR_MINUTO: int = 5  # la respuesta usa el LLM
    LIMITE_BUSQUEDAS_DIARIAS_POR_IP: int = 500
    LIMITE_BUSQUEDAS_DIARIAS: int = 10000  # global: la búsqueda gasta cuota de embeddings (G3)
    LIMITE_RESPUESTAS_DIARIAS_POR_IP: int = 20  # una IP no agota la cuota de todos (G2)
    LIMITE_RESPUESTAS_DIARIAS: int = 200  # global: lo que cuesta el LLM tiene techo
    # G4: respuestas públicas con LLM a la vez; las demás reciben 503 sin ocupar un hilo.
    MAX_RESPUESTAS_PUBLICAS_SIMULTANEAS: int = 2
    # Detrás de Cloudflare Tunnel toda petición llega desde cloudflared: true para leer la IP real
    # de CF-Connecting-IP. Sin túnel, false (si no, cualquiera la falsifica con un encabezado).
    CONFIAR_EN_CF_CONNECTING_IP: bool = False
    # MCP público (/mcp): Host y Origin aceptados (protección contra DNS rebinding del SDK).
    # Al exponerlo (tarea 4.8), agregar el dominio público, ej. ["biblioteca.example.org"].
    MCP_HOSTS_PERMITIDOS: list[str] = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    MCP_ORIGENES_PERMITIDOS: list[str] = ["http://127.0.0.1:*", "http://localhost:*"]

    @field_validator("API_KEY")
    @classmethod
    def _clave_larga(cls, clave: SecretStr) -> SecretStr:
        """G10: vacía cierra lo privado (503); si se define, de verdad."""
        largo = len(clave.get_secret_value())
        if 0 < largo < MIN_LARGO_API_KEY:
            raise ValueError(f"API_KEY necesita al menos {MIN_LARGO_API_KEY} caracteres")
        return clave

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Singleton — importar este en vez de instanciar de nuevo
settings = Settings()  # type: ignore[call-arg]
