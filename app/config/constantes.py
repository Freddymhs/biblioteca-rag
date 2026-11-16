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
MAX_LARGO_ID_EXTERNO = 500
NOMBRE_ARCHIVO_POR_DEFECTO = "sin-nombre"

# Detección por contenido
FIRMA_PDF = b"%PDF-"
# La especificación de PDF tolera basura antes de la firma; los lectores la buscan en el primer KB.
BYTES_BUSQUEDA_FIRMA_PDF = 1024
MAX_BYTES_SUBIDA = 100 * 1024 * 1024  # el PDF más grande del corpus pesa 84 MB
# Holgura para encabezados y separadores del multipart al limitar el cuerpo HTTP completo.
MARGEN_MULTIPART_BYTES = 1024 * 1024

# Lotes en segundo plano (Redis + arq). El corpus agrícola completo pesa 452 MB.
MAX_BYTES_LOTE = 1024 * 1024 * 1024
# Rutas que aceptan un cuerpo de hasta MAX_BYTES_LOTE (el resto, MAX_BYTES_SUBIDA).
PATRON_RUTA_LOTES = r"^/api/espacios/[^/]+/colecciones/[^/]+/lotes$"
# Un archivo por trabajo de arq: el PDF más pesado tarda minutos en Docling y visión.
TIMEOUT_TRABAJO_ARCHIVO_SEGUNDOS = 60 * 60
# Nombres con que se registran las funciones en arq: los usan la API (encola) y el worker.
FUNCION_INGESTAR = "ingestar_archivo"
FUNCION_SINCRONIZAR = "sincronizar_coleccion"
FUNCION_BARRER = "barrer_trabajos_huerfanos"
# Barrido de trabajos huérfanos (worker muerto a mitad o cola perdida). La gracia cubre el
# instante entre crear el trabajo y encolar sus tareas.
GRACIA_HUERFANOS_SEGUNDOS = 10 * 60
MINUTOS_DEL_BARRIDO = set(range(0, 60, 10))

# Conectores (colecciones alimentadas desde otra API)
TIMEOUT_CONECTOR_SEGUNDOS = 30.0

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
# Texto que se le pasa al LLM para extraer datos estructurados (una factura cabe de sobra).
MAX_CARACTERES_EXTRACCION = 12000

# Visión (páginas sin capa de texto). Calibrado el 2026-11-16 con moondream sobre el corpus:
# las páginas en blanco miden 0,0000 de tinta y las que tienen contenido desde 0,04.
ESCALA_DETECCION_BLANCO = 0.5
GRIS_MAXIMO_TINTA = 230  # 0 = negro, 255 = blanco: más claro que esto es papel
PROPORCION_MINIMA_TINTA = 0.005
ESCALA_RENDER_VISION = 1.0
MAX_TOKENS_VISION = 400
# moondream solo entiende inglés; con prompts más largos devolvió respuestas vacías.
PROMPT_VISION = "Describe this image."
# Una página: si Ollama no responde en este tiempo, la página queda sin indexar.
TIMEOUT_VISION_SEGUNDOS = 120.0
TIMEOUT_LLM_SEGUNDOS = 120.0


class TipoDocumento(StrEnum):
    PDF = "pdf"
    TEXTO = "txt"


class ProveedorEmbeddings(StrEnum):
    CLOUDFLARE = "cloudflare"
    OLLAMA = "ollama"


class ProveedorVision(StrEnum):
    NINGUNO = "ninguno"
    OLLAMA = "ollama"


class OrigenTrozo(StrEnum):
    TEXTO = "texto"  # copiado del documento por Docling
    VISION = "vision"  # descripción generada por un modelo de visión
    DATOS = "datos"  # datos estructurados confirmados por una persona (paquete de dominio)


class TipoDecision(StrEnum):
    """Lo que decide el clasificador de una pregunta (FASE_3)."""

    CALCULO = "calculo"
    SIGNIFICADO = "significado"


class RutaRespuesta(StrEnum):
    SEMANTICA = "semantica"  # búsqueda por significado (embeddings) + LLM que redacta con cita
    SQL = "sql"  # herramienta SQL fija de un paquete de dominio; respuesta determinista


class EstadoExtraccion(StrEnum):
    PENDIENTE = "pendiente"  # propuesta del LLM: no se embebe ni la ven las herramientas SQL
    CONFIRMADA = "confirmada"


class TipoTrabajo(StrEnum):
    LOTE = "lote"  # archivos subidos por la API
    SINCRONIZACION = "sincronizacion"  # registros traídos por un conector


class EstadoTrabajo(StrEnum):
    """Se deriva de los contadores; no se guarda."""

    PENDIENTE = "pendiente"
    EN_CURSO = "en_curso"
    TERMINADO = "terminado"


class ProveedorLLM(StrEnum):
    MINIMAX = "minimax"
    OLLAMA = "ollama"  # solo para pruebas locales
