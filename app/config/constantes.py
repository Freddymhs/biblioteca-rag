"""Constantes del motor. Lo que cambia por despliegue va en `settings.py`, no aquí."""

from enum import StrEnum

# bge-m3 produce vectores de 1024 dimensiones. Cambiarlo exige migración y re-embed.
DIMENSION_EMBEDDING = 1024

# Tokenizador con el que HybridChunker mide los trozos: el del mismo modelo que los embebe.
TOKENIZADOR_TROZOS = "BAAI/bge-m3"
MAX_TOKENS_POR_TROZO = 512

# Índice HNSW (valores por defecto de pgvector, explícitos para que la migración los fije).
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 64

# Identificadores de espacio y colección en las URLs: minúsculas, dígitos y guiones.
PATRON_SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_LARGO_SLUG = 64
MAX_LARGO_NOMBRE = 200
MAX_LARGO_NOMBRE_ARCHIVO = 500
MAX_LARGO_MODELO_EMBEDDING = 200  # «proveedor:modelo», ej. cloudflare:@cf/baai/bge-m3
LARGO_SHA256_HEX = 64
NOMBRE_ARCHIVO_POR_DEFECTO = "sin-nombre"

# Detección por contenido
FIRMA_PDF = b"%PDF-"
# La especificación de PDF tolera basura antes de la firma; los lectores la buscan en el primer KB.
BYTES_BUSQUEDA_FIRMA_PDF = 1024
MAX_BYTES_SUBIDA = 100 * 1024 * 1024  # el PDF más grande del corpus pesa 84 MB
# Holgura para encabezados y separadores del multipart al limitar el cuerpo HTTP completo.
MARGEN_MULTIPART_BYTES = 1024 * 1024

# Pregunta
TROZOS_POR_PREGUNTA = 5
MAX_LARGO_PREGUNTA = 2000
RESPUESTA_NO_LO_SE = "No lo sé: la respuesta no está en los documentos de esta biblioteca."
MARCA_NO_LO_SE = "NO_LO_SE"  # lo que el LLM debe contestar si el contexto no alcanza

# Embeddings
LOTE_EMBEDDINGS = 50
TIMEOUT_EMBEDDINGS_SEGUNDOS = 60.0
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4/accounts"

# LLM
MAX_TOKENS_RESPUESTA = 1024
TIMEOUT_LLM_SEGUNDOS = 120.0


class TipoDocumento(StrEnum):
    PDF = "pdf"
    TEXTO = "txt"


class ProveedorEmbeddings(StrEnum):
    CLOUDFLARE = "cloudflare"
    OLLAMA = "ollama"


class ProveedorLLM(StrEnum):
    MINIMAX = "minimax"
    OLLAMA = "ollama"  # solo para pruebas locales
