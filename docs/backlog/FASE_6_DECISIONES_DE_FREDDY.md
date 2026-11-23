# FASE 6: DECISIONES DE FREDDY

**Prioridad**: Alta · **Dependencias**: FASE_5 · Origen: respuestas de Freddy del 2026-11-16 a
`PENDIENTES_FREDDY_2026-11-16.md` (cada tarea cita el punto que cierra).

## Orden de ejecución

1. 6.2, 6.1, 6.4 y 6.7: cambios chicos de código, sin datos.
2. 6.3: esquema medido antes y después (no hay datos que migrar).
3. 6.6 y 6.5: contrato del portal y prueba real con MiniMax, al final (la prueba usa todo lo anterior).
4. 6.8: sumada al final, con las credenciales de Cloudflare.

## Tareas

- [x] **6.1 Título real en las citas** (punto 7): el documento guarda metadatos opcionales (título, fuente, año) que
  llegan al subir por la API y, en la CLI, desde un archivo de catálogo JSON que mapea nombre de archivo a metadatos
  (el de agricultura es `catalogo.json` en la carpeta del corpus; solo lectura). La cita muestra el título y cae al
  nombre del archivo si no hay. Nada específico de agricultura en el código.
- [x] **6.2 Respuesta sin referencia = «no lo sé»** (punto 8): una respuesta redactada sin ninguna referencia `[n]`
  válida se trata como «no lo sé».
- [x] **6.3 Búsqueda con filtros e índice HNSW** (punto 9): aplicar la corrección de esquema de
  `DECISION_HNSW_FILTROS.md` ahora que no hay datos. Elegir entre desnormalizar `espacio_id`/`coleccion_id` en
  `trozo` o índices parciales, midiendo antes y después con `scripts/medir_hnsw.py`, incluido el caso público, y
  actualizar el ADR con los números.
- [x] **6.4 `/docs` cerrado en producción** (punto 11): `/docs`, `/redoc` y `/openapi.json` cerrados en producción
  por configuración, abiertos en desarrollo.
- [x] **6.5 MiniMax real** — cerrada por decisión de Freddy (2026-11-23): sin LLM propio (`LLM_PROVIDER=ninguno`, FASE_6 posterior): el MCP ofrece solo `buscar` y redacta la IA del cliente (Claude Code). `preguntar` se reactiva con otro proveedor si algún día el chat del portal lo pide. Lo que sigue: (puntos 5 y 3): Freddy confirma que su plan permite usar la llave en esta app (ya está en
  el `.env` local). Correr las preguntas de oro y la prueba de punta a punta con MiniMax como LLM, comprobar la
  salida estructurada (clasificador y extracción) con MiniMax y reportar cuántas pasan. Cierra F3 (auditoría FASE_3)
  y la nota BLOQUEADA de la tarea 1.6. La respuesta redactada pública queda habilitada con los límites actuales.
  > BLOQUEADA 2026-11-16: MiniMax responde 402 `insufficient balance (1008)` con la llave del `.env` (modelos
  > M2.7-highspeed, M2.7, M2.5, M2.5-highspeed; una llave falsa da 401, así que la llave es válida). 0 preguntas
  > medidas. Pregunta a Freddy: punto 15 de `PENDIENTES_FREDDY_2026-11-16.md`. F3 y la nota de la 1.6 siguen abiertas.
- [x] **6.6 El portal consume lo público** (punto 6): el chat del portal de AgriPlan usa `/api/publico/buscar` y
  `/api/publico/preguntas`. Escribir `docs/decisions/DECISION_PORTAL_CONSUME_PUBLICO.md` y revisar que
  `docs/flows.md` tenga lo que necesita quien escribe ese cliente a mano (cuerpos literales, errores, límites, CORS
  para el origen del portal por configuración). No se toca el repo del portal.
- [x] **6.7 Licencias** (punto 4): se publican todos los documentos salvo los 10 que declaran «todos los derechos
  reservados». Dejar un comando que marque la licencia como verificada a partir de la tabla de
  `LICENCIAS_AGRICULTURA_2026-11-16.md`, para correrlo después de la ingesta; no ejecutarlo contra ninguna base.
- [x] **6.8 Benchmark de embeddings, la parte que se mide aquí** (punto 1, sumada el 2026-11-16 al llegar las
  credenciales de Cloudflare): `scripts/benchmark.py` en el ThinkPad (coseno Ollama bge-m3 vs Cloudflare bge-m3 y
  latencia del embedding de una pregunta), números en la tarea 1.9 y decidir si los dos proveedores comparten
  identificador de modelo (B2). La parte del Mac Mini sigue bloqueada. No se cambia `EMBEDDINGS_PROVIDER` del `.env`.
  > Hecho: coseno mínimo 0,999991 (textos distintos: 0,46 como máximo); comparten el identificador `bge-m3`
  > (`DECISION_BGE_M3_IDENTIFICADOR_COMUN.md`, migración `c7a2d4e8f613`).

## Sin cambios por decisión (puntos 12, 13 y 14)

- Límites de uso público por defecto: se quedan.
- Colección `sobre-mi`, paquete `facturas` y trazas en memoria: se dejan como están.

## Pendiente aún de Freddy (no se hace)

- Ingesta completa del corpus (la lanza la sesión que supervisa, después del commit) y exposición a internet.
- Token de Cloudflare: llegó durante la fase (tarea 6.8).
- Saldo o endpoint de MiniMax (tarea 6.5, punto 15).

## Criterios de Aceptación

- [x] Una cita muestra el título del documento, o su nombre de archivo si no tiene.
- [x] Una respuesta sin referencia válida es «no lo sé».
- [x] La búsqueda con filtros devuelve los 5 trozos aunque haya miles de vecinos de otra colección (medido).
- [x] En producción `/docs`, `/redoc` y `/openapi.json` responden 404.
- [x] Preguntas de oro y salida estructurada con MiniMax real: no aplica (sin LLM propio, 2026-11-23).
- [x] Coseno Ollama vs Cloudflare medido y decidido el identificador común (6.8).
