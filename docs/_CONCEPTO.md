> Origen: DEVELOPMENT/concept-rag-template.md (ideación). Carpeta del proyecto: biblioteca-rag (2026-10-24).

# concept-rag-template

> Concepto durable (`/work:resume:new-concept`, 2026-09-27). Solo documentación: sin carpeta, sin código,
> sin tocar resume.json. Cuando se construya, `/work:resume:new-project` copia este archivo tal cual a
> `docs/_CONCEPTO.md`.
> Origen de la idea: transcripción de un video de YouTube ("tu primer RAG con Next.js + Postgres + pgvector",
> app de facturas desplegada vía MCP). Este concepto NO replica ese proyecto: toma el patrón y lo vuelve template.
> Concepto hermano, distinto: `concept-docvoice.md` (RAG con respuesta en voz, Chroma). No se fusionan.

## Propósito

Motor RAG **genérico y self-hosted** para reutilizar en todos los proyectos futuros: un solo motor, muchas
bibliotecas de conocimiento. Responde **con cita al documento de origen**, o "no lo sé" cuando la respuesta no
está en los datos. Primer uso real: la biblioteca agrícola (`PRODUCTION/BIBLIOTECAPARARAG-AGRICULTURA/`).
A futuro: memoria larga de Hermes ("uno que sepa todo sobre mí").

## Qué es / Qué no es

| Es | No es |
|---|---|
| Template reutilizable: el dominio es data (colecciones), no código | La app de facturas del video |
| Un deploy, organizado en **espacio → colecciones** | Un RAG por tema con deploy propio, ni uno solo que mezcla todo |
| Self-hosted en el Mac Mini, detrás de Tailscale | SaaS público o multiusuario |
| Proveedores intercambiables por configuración (LLM, embeddings, visión) | Atado a un proveedor |
| Respuestas con cita + "no lo sé" | Chat general que improvisa |

## Modelo de dominio

```
espacio            (laboral · personal · estudios — las 3 áreas de vida)
  └── coleccion    (= verticales del fact_store de Hermes: agricultura, programacion, cocina, licencia-conducir...)
        └── documento     (archivo subido o registro traído por un conector; hash de contenido = no se re-ingesta)
              └── trozo   (texto original + embedding + embedding_model + página/origen para la cita)
```

- Una pregunta se acota a un espacio (busca en todas sus colecciones) o a una colección puntual.
- `espacio` y `coleccion` existen en el esquema **desde F1**, aunque al principio se use uno solo: agregarlos
  después obliga a migrar y re-etiquetar todo lo guardado.
- Se guarda siempre el **texto original** de cada trozo y **qué modelo lo embebió**. Es lo que permite cambiar de
  modelo o de troceo re-embebiendo por script, sin volver a subir ni extraer.
- **Data de un empleador o cliente = otra instancia** del mismo template (otro deploy), nunca un espacio más en
  la infraestructura personal.

### Flujo

```
INGESTA:  archivo / conector → detectar tipo por contenido (no por extensión)
          → Docling: texto + tablas (páginas con texto)
          → páginas sin texto: F1 = log · F2 = modelo de visión
          → HybridChunker (respeta tablas y títulos) → bge-m3 → Postgres/pgvector
          (documento + trozos en una sola transacción)

PREGUNTA: pregunta + espacio/colección → embedding bge-m3 → pgvector (filtro por espacio/colección, índice HNSW)
          → MiniMax redacta con los trozos como contexto, temperatura 0 → respuesta + citas (documento, página)
          → sin trozos relevantes → "no lo sé"
```

## Stack

| Pieza | Decisión | Fuente |
|---|---|---|
| Arquitectura | API **FastAPI** (Python) + front **Next.js** separados | `[gap]` oferta IBM/Codelco pide Python+FastAPI+LLMs; Get on Board: `fastapi` 9 ofertas (2026-09-26) · `[norte]` FastAPI, Python |
| Base de datos | **Postgres + pgvector**: tablas y vectores en la misma base (cita = JOIN) | `[feature]` · `[gap]` PostgreSQL en 4 ofertas; experiencia real declarada Postgres+Prisma (`interview-gaps.yaml:937,1021`) |
| Framework RAG | **LangChain** (`langchain-postgres` → `PGVectorStore`; `PGVector` está deprecado desde v0.0.14). **LangGraph recién en F3** | `[research]` Get on Board: `langchain` 4 ofertas, `llamaindex` 0, `langgraph` 3 (Bci, Niuro, 3IT); SO Survey 2025: 32,9% vs 13,3%. Job-radar propio pondera `langchain: 3` (`job-rada-latam/job1/config.py:118`) |
| LLM | **MiniMax** por endpoint compatible con Anthropic (`https://api.minimax.io/anthropic`, `MINIMAX_PLAN_SECRET`): `MiniMax-M2.7-highspeed` por defecto, `MiniMax-M3` si hace falta. Configurable (`init_chat_model`) | `[feature]` plan mensual ya pagado, cero costo extra (`~/bin/llm`) |
| Embeddings | Modelo **`bge-m3`** (open source, multilingüe). Proveedor por defecto **Cloudflare Workers AI** (`@cf/baai/bge-m3`); respaldo **Ollama local**, mismo modelo | `[research]` Cloudflare: 10.000 neurons/día gratis, renovables; bge-m3 = 1.075 neurons por millón de tokens → ~9,3M tokens/día (página oficial de precios, 2026-09-26). Gemini free tier usa los datos para entrenar (descartado) |
| Extracción | **Docling** (MIT): texto + **tablas**; `HybridChunker`. Visión solo para páginas sin texto (F2) | `[feature]` medido en el corpus: 131 PDFs, 5.186 páginas, ~251 escaneadas (~5%); 4 archivos sin extensión; muchas tablas (Kc, fertilización) |
| Acceso a datos | SQLAlchemy 2 + Alembic | `[feature]` |
| Tooling Python | uv · ruff · pyright | `[feature]` |
| Front | Next.js + Tailwind + shadcn/ui + TanStack Query; tipos generados desde el OpenAPI de FastAPI (`openapi-typescript`) | `[feature]` · `[gap]` Next.js en 8 ofertas |
| Tests | pytest + testcontainers (Postgres/pgvector real) + **preguntas de oro por colección** (incluye una sin respuesta → debe decir "no lo sé") | `[norte]` testing (Jest/Supertest en wishlist) · `[feature]` |
| Deploy | **Docker Compose en el Mac Mini**, acceso por Tailscale, sin auth en F1 | `[feature]` servidor 24/7 ya existente (Hermes); $0; data personal no sale de casa |

### Reglas de diseño que sostienen el "template"

1. **El dominio no vive en el código.** Colección nueva = data/config, nunca un fork.
2. **Proveedores detrás de interfaces de LangChain** (`BaseChatModel`, `Embeddings`). Cambiar proveedor = una
   línea de `.env`. No se usan productos propietarios de Cloudflare (Vectorize, Workers, AI Gateway): Cloudflare
   solo convierte texto en vectores y no guarda nada.
3. **Texto original + `embedding_model` por trozo.** Cambiar de modelo = script de re-embed; nunca se mezclan
   vectores de modelos distintos en una búsqueda.
4. **Determinista primero, IA solo donde hace falta.** El texto que ya está en el PDF se copia con una librería;
   el modelo de visión solo "mira" lo que no tiene texto. En números, un parser no se equivoca y un modelo sí.
5. **Cálculos por SQL, significado por embeddings** (F3). El LLM nunca escribe SQL libre: elige entre
   herramientas SQL fijas.

## Practice-wishlist (lo que este concepto entrena)

### Gaps que cierra
- `[gap]` **Python + FastAPI + LLMs**: oferta IBM/Codelco (`interview-gaps.yaml`, slug `muck-ibm-fullstack-ia-2026-07`), P3-LLMs-chatbot-Depot.
- `[gap]` **LangChain / LangGraph**: Bci, Improving, Niuro, 3IT (Get on Board, 2026-09-26).
- `[gap]` **Docker**: 5 ofertas en `stack_pedido`/`stack_deseables`.
- `[gap]` **PostgreSQL**: 4 ofertas.
- `[gap]` + `[norte]` **Row Level Security**: norte ×2 y gap declarado "RLS no usado en producción" (Somarco) → F4.

### NORTE que practica
- `[norte]` **Redis** (#1 por frecuencia): cola de ingesta en background → F2.
- `[norte]` **DB indexing**: índice HNSW de pgvector → F1.
- `[norte]` **Transaction isolation levels**: documento + trozos atómicos → F1.
- `[norte]` **MCP protocol**: Hermes ↔ RAG → F4.
- `[norte]` **OpenTelemetry / Grafana**: trazas por pregunta → F5.

## Fases (F1 PROTEGIDO)

### F1 — Motor semántico con cita, colección `agricultura` (1 sprint = 2 semanas)
Mínimo que entrega valor real: preguntarle a la biblioteca agrícola y recibir respuesta con cita.
- [ ] `docker compose`: Postgres/pgvector + API FastAPI. `.env.example` con todos los proveedores.
- [ ] Esquema con `espacio`, `coleccion`, documento (hash de contenido), trozo (texto, embedding, `embedding_model`, página). Migración Alembic. Índice HNSW.
- [ ] Ingesta por **CLI** (carpeta completa) y por **endpoint** (un archivo). Detección de tipo por contenido. Documento + trozos en una sola transacción.
- [ ] Docling + `HybridChunker`. Páginas sin texto → **log** (no se indexan todavía).
- [ ] Embeddings `bge-m3` vía Cloudflare Workers AI.
- [ ] Endpoint de pregunta: búsqueda filtrada por espacio/colección → MiniMax (temperatura 0) → respuesta + citas; "no lo sé" si no hay contexto relevante.
- [ ] Front Next.js: **una sola página** (subir, elegir colección, preguntar, ver la cita). Sin pulir.
- [ ] Tests: pytest + testcontainers; preguntas de oro de `agricultura`, incluida una sin respuesta.
- [ ] **Benchmark en el Mac Mini**: Ollama `bge-m3` vs Cloudflare → similitud coseno del mismo texto >0,99 (si no pasa, el respaldo implica re-embed); embedding de pregunta <1 s; ingesta completa en una noche.
- [ ] README con "cómo crear una colección nueva".

**Definition of Done F1**: `git clone` → `cp .env.example .env` → `docker compose up` → subir un PDF → respuesta con cita en **<15 minutos**, siguiendo solo el README.

### F2 — Ingesta completa y conectores
- [ ] Modelo de visión para páginas sin texto (confirmar si el plan de MiniMax acepta imágenes; si no, proveedor alternativo configurable).
- [ ] Ingesta en background: Redis + arq, con progreso visible en el front.
- [ ] Conectores HTTP: colección `sobre-mi` desde `fmarcosdev.api.resume` (re-sync manual o programado; la copia indexada puede quedar desfasada de la fuente).
- [ ] Script de re-embed (cambio de modelo o de troceo desde el texto guardado).

### F3 — Paquetes de dominio y enrutamiento
- [ ] Contrato de paquete de dominio: esquemas Pydantic por tipo de documento → extracción estructurada + validación; formulario de confirmación generado desde el JSON Schema. Solo se embebe lo confirmado.
- [ ] Registro de herramientas SQL por colección + **LangGraph**: nodo clasificador "cálculo vs significado" → herramientas SQL fijas o búsqueda semántica.
- [ ] Paquete `facturas` (el caso del video) como ejemplo de referencia.

### F4 — Hermes y aislamiento
- [ ] Servidor MCP del RAG para que Hermes lo consulte desde Telegram (memoria larga).
- [ ] Row Level Security por espacio; rol restringido para Hermes.

### F5 — Observabilidad y deploy opcional
- [ ] Trazas por pregunta: Langfuse self-hosted u OpenTelemetry + Grafana.
- [ ] Deploy público opcional (Railway o AWS). Exponer a internet exige auth antes.

## Fuera de alcance v1
- Multiusuario, autenticación, exposición a internet.
- Text-to-SQL (el LLM escribiendo SQL libre).
- Respuesta en voz (es `concept-docvoice.md`).
- Productos propietarios de un proveedor (Vectorize, etc.).

## Riesgos
- **Gold-plating**: el stack es ancho para escribirlo a mano ("proyectos = experiencia honesta, escribo cada línea",
  `~/Documents/system-debug/CARRERA.md`). Mitigación: todo lo marcado como norte vive en F2 o después; LangGraph
  entra recién en F3; front de F1 = una página.
- **Dependencia de dos regalos**: cuota del plan MiniMax (ventanas de 5h y semanal, compartidas con el trabajo de
  código; se agotó el 2026-09-12) y free tier de Cloudflare. Mitigación: LLM configurable; Ollama como respaldo de
  embeddings con el mismo modelo.
- **Términos del plan MiniMax**: es un "coding plan"; no verificado si permite usar la llave en una app propia.
- **Dos lenguajes** (Python + TypeScript): costo aceptado por mercado; el contrato OpenAPI → TS evita la deriva.
- **Privacidad por espacio**: el espacio `personal` puede requerir proveedores locales (Ollama) si se decide que
  esa data no sale de casa.

## Notas para el siguiente paso
- Construir: `/work:resume:new-project` sobre este concepto (template-first, carpeta, git, draft en resume.json).
- Corpus de prueba del F1: `PRODUCTION/BIBLIOTECAPARARAG-AGRICULTURA/` (131 PDFs + `.txt` + `.html` + 4 sin extensión;
  `arandano-fenologia-*.pdf` pesa 2 KB, probablemente vacío).
- Plan relacionado: `ParaPymes/docs/backlog/FASE_6_CT_ANALYTICS_RAG_BI.md` planeaba LlamaIndex + OpenAI embeddings;
  lo aprendido aquí (LangChain, bge-m3) sirve para replantearla cuando se retome.
