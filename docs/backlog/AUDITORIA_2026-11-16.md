# Auditoría del 2026-11-16 — FASE_0 y FASE_1, antes del primer commit

Auditó una sesión distinta a la que escribió el código: 56 archivos leídos completos. `make check` ya pasaba
(57 tests, 7 saltados); nada de esta lista lo detectaban los tests. Los puntos de la parte A se comprobaron después
abriendo el archivo.

## A. Se corrige antes del commit

Cada punto se cierra con su test (que falle sin el arreglo) y `make check` en verde. Marcar la casilla al cerrarlo.

- [x] **A1 Respuesta vacía del LLM** — `app/services/pregunta.py`, función `preguntar`: si el LLM devuelve texto
  vacío se responde `sabe=True` con `respuesta=""` y todas las citas. Debe tratarse como falla del proveedor o como
  «no lo sé», nunca como respuesta válida.
- [x] **A2 Errores de formato del proveedor de embeddings** — `app/providers/embeddings.py`,
  `_vectores_de_respuesta_openai` y `ERRORES_DE_PROVEEDOR`: un cuerpo que no es JSON o un ítem sin `index` o
  `embedding` lanza `ValueError`/`KeyError`/`TypeError` y sale como 500. Debe salir como `ErrorEmbeddings` (502).
- [x] **A3 Nombre de archivo sin validar** — `app/routers/documentos.py` y `app/models/documento.py`: un nombre de
  más de 500 caracteres o con un byte NUL revienta en el commit como 500. Validar y responder 422; el largo máximo y
  el nombre por defecto (`"sin-nombre"`) van como constantes.
- [x] **A4 El límite de tamaño llega tarde** — `app/routers/documentos.py`: `archivo.file.read(MAX + 1)` corre cuando
  Starlette ya recibió y guardó en disco el cuerpo entero. Rechazar por `Content-Length` antes de leer el cuerpo
  (dependencia o middleware) y dejar el chequeo actual como segunda barrera.
- [x] **A5 Conexión abierta durante la extracción** — `app/services/ingesta.py`: el comentario dice que la
  transacción no espera a la red, pero las lecturas previas (`obtener_coleccion`, `_rechazar_si_ya_existe`) ya la
  abrieron y queda «idle in transaction» durante Docling y los embeddings. Cerrar esa transacción de lectura antes
  de extraer y corregir el comentario.
- [x] **A6 CORS abierto por defecto** — `main.py`: `settings.CORS_ORIGINS or ["*"]` convierte la lista vacía en
  «cualquier origen». Con lista vacía no se permite ningún origen cruzado. Actualizar `.env.example`.
- [x] **A7 Puertos publicados a toda la red** — `docker-compose.yml`: Postgres (`postgres/postgres`) y la API sin
  autenticación quedan en `0.0.0.0`. Publicar en `127.0.0.1` y sacar la contraseña a una variable con valor por
  defecto solo para desarrollo.
- [x] **A8 Página de la cita cuando un trozo cruza páginas** — `app/services/extraccion.py`, `_piezas`: un trozo que
  Docling entrega con elementos de dos páginas se cita con la menor. Partirlo por página o guardar el rango
  (`pagina_inicio`, `pagina_fin`). Si se cambia el esquema, se edita la migración inicial: todavía no hay datos.
- [x] **A9 Una sola fuente** — `app/cli/ingestar.py`: `CODIGO_DUPLICADO = 409` repite el código de
  `app/common/errors.py` y detecta duplicados comparando enteros; usar una excepción propia. `main.py`:
  `version="0.1.0"` repite `pyproject.toml`.
- [x] **A10 Números y cadenas sueltos** — códigos HTTP literales en `app/common/errors.py` (usar `http.HTTPStatus`);
  largos de columna repetidos en `app/models/` que ya existen en `app/config/constantes.py`; prefijos `"ollama:"` y
  `"cloudflare:"` en `app/providers/embeddings.py`, que deben salir del enum de proveedores.
- [x] **A11 Tipos de retorno que faltan** — handlers de `app/routers/*.py` y de `main.py`; los `# type: ignore` de
  `main.py` sin comentario que los justifique.
- [x] **A12 Comentarios de la plantilla** — `app/config/database.py`, `app/config/settings.py`, `alembic/env.py`,
  `alembic.ini`: siguen hablando de Prisma, de Joi y de «this template».
- [x] **A13 `scripts/e2e_local.py`** — `_esperar_api` no espera cuando la API responde algo distinto de 200 y agota
  los 60 intentos al instante; `alembic` se llama por `PATH` en vez de `sys.executable -m alembic`.

## B. Abierto, no bloquea este commit

Son riesgos reales sin medir, o decisiones de producto. Cada uno indica dónde se resuelve.

- **B1 Sin `[n]` válido se devuelven todas las citas** (`_citas_referidas`). La respuesta sale como verificada sin
  que nadie comprobara el respaldo. Decisión de Freddy: ¿se exige al menos una referencia válida?
- **B2 Cambiar de proveedor de embeddings deja el corpus invisible** — `ollama:bge-m3` y `cloudflare:@cf/baai/bge-m3`
  son identificadores distintos del mismo modelo, el hash impide reingestar y no existe el re-embed. → tarea 2.4, y
  el resultado del benchmark de la 1.9.
  > Resuelto 2026-11-16 (FASE_6, 6.8): coseno 0,999991 → identificador común `bge-m3`
  > (`DECISION_BGE_M3_IDENTIFICADOR_COMUN.md`).
- **B3 Índice HNSW con filtros** — pgvector filtra después de buscar en el índice; con más espacios o más datos puede
  devolver menos de 5 trozos y producir «no lo sé» falsos. Medir con el corpus completo; evaluar
  `hnsw.iterative_scan`. → antes de cerrar la FASE_2.
- **B4 Docling compartido entre hilos** — `_conversor()` y `_chunker()` se usan desde el threadpool sin candado. No se
  sabe si es seguro. → tarea 2.2 (ingesta en segundo plano).
- **B5 Inyección por el contenido de un PDF** — los fragmentos entran al prompt sin delimitar. → FASE_4, antes de
  exponer nada.
- **B6 Contenedor** — sin migración automática ni `HEALTHCHECK`; `--workers 2` carga Docling dos veces; los modelos se
  descargan en la primera subida. → FASE_4, tarea 4.8.
- **B7 `SECRET_KEY` es obligatoria y no se usa**; `ollama` y `anthropic` se importan sin estar declarados en
  `pyproject.toml`. → revisar en la FASE_4 (auth).
- **B8 Un `.txt` que contenga `%PDF-` en su primer KB se clasifica como PDF** (`app/services/deteccion.py`).
- **B9 Tests que faltan** — el 413 por HTTP, la carrera `IntegrityError` de la ingesta y el caso sin `[n]`.

## No verificado por la auditoría

- El build de Docker (si la imagen base trae `adduser`, si Docling necesita librerías del sistema).
- El contrato real de Cloudflare `/ai/v1/embeddings` contra su documentación.
- Si `_paginas_sin_texto` cuenta como «con contenido» una página que solo tiene una imagen.
