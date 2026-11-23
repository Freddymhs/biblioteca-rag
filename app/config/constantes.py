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
MAX_LARGO_MODELO_EMBEDDING = 200  # «proveedor:modelo» o el común de MODELOS_EQUIVALENTES
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

# D1: lo pesado no se convierte en la petición HTTP (Docling ocupa un hilo por minutos y su
# candado es por proceso): va por la cola, donde el worker convierte de a uno.
MAX_BYTES_SUBIDA_SINCRONA = 10 * 1024 * 1024
MAX_PAGINAS_SUBIDA_SINCRONA = 30

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
# F1: un cálculo sobre miles de facturas no devuelve miles de citas.
MAX_CITAS_CALCULO = 20
MAX_LARGO_PREGUNTA = 2000
RESPUESTA_NO_LO_SE = "No lo sé: la respuesta no está en los documentos de esta biblioteca."
MARCA_NO_LO_SE = "NO_LO_SE"  # lo que el LLM debe contestar si el contexto no alcanza
# K1: un rango de referencias ([1-3]) no se expande más allá de los fragmentos que se entregan:
# [1-999999] no crea un millón de números.
MAX_NUMEROS_POR_RANGO_REFERENCIA = TROZOS_POR_PREGUNTA
# K1: dígitos de un número de referencia. Uno más largo no es referencia: int() de Python revienta
# pasados 4300 dígitos (un 500). Nueve dejan pasar rangos como [1-999999], que se recortan arriba.
MAX_DIGITOS_REFERENCIA = 9

# Embeddings
LOTE_EMBEDDINGS = 50
TIMEOUT_EMBEDDINGS_SEGUNDOS = 60.0
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4/accounts"

# LLM
MAX_TOKENS_RESPUESTA = 1024
# Texto que se le pasa al LLM para extraer datos estructurados (una factura cabe de sobra).
MAX_CARACTERES_EXTRACCION = 12000

# Servicio público (FASE_4). Roles de Postgres: los crea la migración `servicio publico`.
# Grupo sin login con las políticas RLS: solo ve colecciones públicas y documentos con licencia
# verificada. El usuario con login de la API pública y el MCP (DATABASE_URL_PUBLICA) es miembro.
ROL_PUBLICO = "biblioteca_publico"
MAX_LARGO_LICENCIA = 200
# Tabla de licencias con veredicto (6.7): columnas que lee `app.cli.licencias`.
COLUMNA_ARCHIVO_LICENCIAS = "Archivo"
COLUMNA_PROPUESTA_LICENCIAS = "Propuesta"
COLUMNA_VEREDICTO_LICENCIAS = "Veredicto"
# K3: un veredicto es «decisión[: motivo] [(quién, cuándo)]»; la decisión se compara exacta, sin
# mayúsculas. Cualquier otra forma es un error que nombra la línea.
VEREDICTO_PUBLICAR = "publicar"
VEREDICTO_NO_PUBLICAR = "no publicar"
SEPARADOR_MOTIVO_VEREDICTO = ":"
# Código de salida de una CLI que terminó, pero con algo que revisar (no es el 0 de «todo bien»).
SALIDA_CON_ERRORES = 1
# Metadatos opcionales de un documento (FASE_6, 6.1): llegan al subir o desde un catálogo JSON.
MAX_LARGO_TITULO_DOCUMENTO = 500
MAX_LARGO_FUENTE_DOCUMENTO = 300
ANNO_MINIMO_DOCUMENTO = 1000
ANNO_MAXIMO_DOCUMENTO = 2100
# K4: categoría Unicode de los caracteres de control (NUL, campana, salto de línea…): un título o
# una fuente que los trae se rechaza (422 en la API); Postgres ni acepta el NUL.
CATEGORIA_UNICODE_CONTROL = "Cc"
# En un catálogo en forma de lista, el campo que nombra el archivo.
CLAVE_ARCHIVO_CATALOGO = "archivo"
ENCABEZADO_API_KEY = "X-API-Key"
# Documentación interactiva (6.4): se publica solo si DOCUMENTACION_API está encendida.
RUTA_DOCS = "/docs"
RUTA_REDOC = "/redoc"
RUTA_OPENAPI = "/openapi.json"
# Trazas (FASE_5): con este id se busca la traza de una respuesta en Jaeger.
ENCABEZADO_TRAZA = "X-Traza-Id"
NOMBRE_SERVICIO_TRAZAS = "biblioteca-rag"
# I5: nombre del span HTTP cuando la ruta no es de la app (un escáner que prueba URLs).
NOMBRE_SIN_RUTA = "(sin ruta)"
# Dónde deja TrazaHTTP el contexto de la traza en el `scope` (para las tools del MCP).
CLAVE_CONTEXTO_TRAZA = "biblioteca_rag.traza"
# Cuánto espera el exportador al vaciar sus spans pendientes (valor por defecto del SDK).
ESPERA_VACIADO_TRAZAS_MS = 30000
# G10: lo que da secrets.token_urlsafe(32) es más largo; menos que esto se adivina.
MIN_LARGO_API_KEY = 32
PREFIJO_API = "/api/"
PREFIJO_PUBLICO = "/api/publico"
RUTA_MCP = "/mcp"
# G1: lo público y el MCP reciben JSON chico (una pregunta cabe en 2.000 caracteres).
MAX_BYTES_CUERPO_PUBLICO = 16 * 1024
# G13: ninguna consulta pública ocupa la base más que esto.
TIMEOUT_CONSULTA_PUBLICA_MS = 5000
PATRONES_RUTA_PUBLICA = (r"^/api/publico(/|$)", r"^/mcp(/|$)")
# Límite de uso (Redis). Ventanas fijas desde el primer uso: sin bordes de minuto que reiniciar.
VENTANA_POR_IP_SEGUNDOS = 60
SEGUNDOS_POR_DIA = 24 * 60 * 60
VENTANA_DIARIA_SEGUNDOS = SEGUNDOS_POR_DIA
PREFIJO_LIMITE = "limite"
# Uso público (tarea 5.2): contadores por día, sin IPs, retenidos este tiempo.
PREFIJO_USO = "uso"
RETENCION_USO_DIAS = 90
DIAS_USO_POR_DEFECTO = 7
# Lo pone Cloudflare Tunnel con la IP real del visitante; solo se cree si se configura (4.8).
ENCABEZADO_IP_CLOUDFLARE = "CF-Connecting-IP"

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


# B2 (tarea 6.8): el mismo modelo en dos proveedores da el mismo vector (coseno mínimo 0,999991
# sobre los textos de `scripts/benchmark.py`) y comparte identificador en `trozo.embedding_model`:
# cambiar de proveedor no deja el corpus invisible ni obliga a re-embeber. Solo pares medidos.
MODELO_BGE_M3 = "bge-m3"
MODELOS_EQUIVALENTES: dict[tuple[ProveedorEmbeddings, str], str] = {
    (ProveedorEmbeddings.OLLAMA, "bge-m3"): MODELO_BGE_M3,
    (ProveedorEmbeddings.CLOUDFLARE, "@cf/baai/bge-m3"): MODELO_BGE_M3,
}


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


class UsoPublico(StrEnum):
    """Cada uso público cuenta en su propio límite por IP."""

    BUSQUEDA = "busqueda"  # fragmentos con cita, sin LLM
    RESPUESTA = "respuesta"  # redactada por el LLM: además, tope diario global


class EtapaTraza(StrEnum):
    """Spans de una pregunta (tarea 5.1); su duración es la latencia de la etapa."""

    PREGUNTAR = "preguntar"
    BUSCAR_PUBLICO = "buscar_publico"
    EMBEBER = "embeber_pregunta"
    BUSCAR = "buscar_trozos"
    REDACTAR = "redactar"
    DESCRIBIR_IMAGEN = "describir_imagen"  # visión de una página sin texto (I9)
    CLASIFICAR = "clasificar"
    CALCULAR = "calcular_sql"


class AtributoTraza(StrEnum):
    """Lo que guarda una traza. A propósito NO hay atributo para el texto ni para la IP."""

    ALCANCE = "biblioteca.alcance"
    PREGUNTA_LARGO = "biblioteca.pregunta.largo"
    ESPACIO = "biblioteca.espacio"
    COLECCION = "biblioteca.coleccion"
    PROVEEDOR_EMBEDDINGS = "biblioteca.proveedor.embeddings"
    PROVEEDOR_LLM = "biblioteca.proveedor.llm"
    TROZOS_CANDIDATOS = "biblioteca.trozos.candidatos"
    DISTANCIAS = "biblioteca.trozos.distancias"
    TROZOS_USADOS = "biblioteca.trozos.usados"
    SABE = "biblioteca.sabe"
    RUTA = "biblioteca.ruta"
    DECISION = "biblioteca.decision"
    HERRAMIENTA = "biblioteca.herramienta"
    CODIGO_HTTP = "http.response.status_code"  # convención semántica de OpenTelemetry
    TIPO_ERROR = "error.type"  # ídem: solo el tipo de la excepción, nunca su mensaje


class ContadorUso(StrEnum):
    """Contadores diarios del uso público (5.2). No «429»: se confundía con el código HTTP."""

    SERVIDAS = "servidas"  # consultas respondidas (I4: contadas al final, no al reservar)
    RECHAZADAS = "rechazadas"  # 429 emitidos


class AlcanceTraza(StrEnum):
    PUBLICO = "publico"
    PRIVADO = "privado"
    OTRO = "otro"


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
