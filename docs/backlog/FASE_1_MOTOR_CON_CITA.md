# FASE 1: MOTOR CON CITA — colección `agricultura`

**Prioridad**: Alta (protegida) · **Dependencias**: FASE_0 · = F1 de `_CONCEPTO.md`

## Orden de ejecución

1. Tarea 1.1 — esquema que todo lo demás usa.
2. Tareas 1.2, 1.3, 1.4 — piezas de la ingesta.
3. Tarea 1.5 — depende de 1.2–1.4.
4. Tarea 1.6 — depende de 1.4 y 1.5. Resto al final.

## Tareas

- [x] **1.1 Esquema**: espacio → colección → documento (hash, tipo, páginas) → trozo (texto, embedding, `embedding_model`, página). Migración Alembic + índice HNSW. `app/models/`.
- [x] **1.2 Detección**: tipo por contenido (no extensión) + hash → rechaza basura y duplicados. `app/services/deteccion.py`.
- [x] **1.3 Extracción**: Docling (texto + tablas) + `HybridChunker`; páginas sin texto → log. `app/services/extraccion.py`.
- [x] **1.4 Embeddings**: interfaz LangChain `Embeddings`; bge-m3 vía Cloudflare, Ollama por `.env`. `app/providers/embeddings.py`.
- [x] **1.5 Ingesta**: documento + trozos en una transacción. Endpoint (un archivo) y CLI (carpeta). `app/routers/documentos.py`, `app/cli/ingestar.py`.
- [x] **1.6 Pregunta**: filtro espacio/colección → pgvector → MiniMax (temp 0) → respuesta + citas; sin contexto relevante → «no lo sé». `app/services/pregunta.py`, `app/providers/llm.py`.
  > Pendiente 2026-11-16: llamada real a MiniMax sin probar (falta la llave en uso y confirmar los términos del plan). Probado con dobles y con Ollama local.
- [x] **1.7 Espacios y colecciones**: endpoints mínimos de alta y listado.
- [x] **1.8 Preguntas de oro** de `agricultura`, incluida una sin respuesta. `tests/oro/`.
  > 2026-11-16: 7 preguntas sobre 6 documentos del corpus. Con Ollama local (bge-m3 + llama3.2:3b) pasan 6 de 7; ver criterio 3.
- [ ] **1.9 Benchmark Mac Mini**: coseno Ollama vs Cloudflare > 0,99; embedding de pregunta < 1 s; los 89 documentos en una noche (desde el 2026-11-15 son 89, no 90). `scripts/benchmark.py`.
  > BLOQUEADA 2026-11-16: falta de Freddy el token y account id de Cloudflare (coseno Ollama vs Cloudflare) y su visto bueno para correr en el Mac Mini (latencia allí y los 89 documentos en una noche). Hecho aquí: `scripts/benchmark.py`; en el ThinkPad, pregunta con Ollama bge-m3 = 0,203 s (mediana de 10).
- [x] **1.10 README**: cómo crear una colección nueva.

## Criterios de Aceptación

- [ ] `git clone` → `.env` → `docker compose up` → subir un PDF → respuesta con cita en < 15 min, solo con el README (vía Swagger).
  > Sin cerrar 2026-11-16: el camino completo se probó con `scripts/e2e_local.py` (API + CLI + base desechable, 6 documentos y 7 preguntas en ~10 min). No se migró la base de `docker compose`: el permiso de la sesión lo bloqueó. Falta recorrerlo una vez por Swagger con la base de compose.
- [x] Un archivo vacío o con tipo falso se rechaza; el mismo archivo dos veces no duplica trozos.
- [ ] Las preguntas de oro pasan, incluida la que debe responder «no lo sé».
  > BLOQUEADA 2026-11-16: falta la llave de MiniMax en uso (el LLM previsto). Con llama3.2:3b local pasan 6 de 7: la del granado respondió en cirílico, copiando el documento.
