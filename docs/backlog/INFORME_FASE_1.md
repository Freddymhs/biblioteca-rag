# Informe FASE_1 — MOTOR CON CITA (9/10, 1.9 bloqueada)

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Auditada antes del commit
(`AUDITORIA_2026-11-16.md`); la parte A quedó corregida (ver «Corregido tras la auditoría»).

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 1.1 Esquema | `espacio → coleccion → documento → trozo`; `Vector(1024)`; HNSW `vector_cosine_ops` (m=16, ef_construction=64); migración `4c0ae2807286` con `CREATE EXTENSION` y downgrade que borra el enum |
| 1.2 Detección | firma `%PDF-` en el primer KB o UTF-8 legible; vacío/binario/latin-1 → 422; > 100 MB → 413; SHA-256 |
| 1.3 Extracción | Docling sin OCR, con tablas; `HybridChunker` con tokenizador `BAAI/bge-m3` (512 tokens); piezas de páginas distintas no se unen; cada trozo guarda su rango `pagina_inicio`–`pagina_fin`; páginas sin texto al log |
| 1.4 Embeddings | `CloudflareEmbeddings` propio contra `/ai/v1/embeddings` (OpenAI-compatible) y `OllamaEmbeddings`; se elige con `EMBEDDINGS_PROVIDER` |
| 1.5 Ingesta | documento + trozos en un commit; 409 por hash (chequeo temprano + restricción única); endpoint `POST …/documentos` y CLI `app.cli.ingestar` |
| 1.6 Pregunta | filtro espacio/colección **y** `embedding_model`; distancia ≤ 0,55 o «no lo sé» sin llamar al LLM; LLM temp 0; citas = las que el LLM marcó con `[n]` |
| 1.7 Catálogo | alta y listado de espacios y colecciones |
| 1.8 Oro | `tests/oro/agricultura.json`: 7 preguntas (1 sin respuesta) con documento y página esperados |
| 1.9 Benchmark | **BLOQUEADA**: `scripts/benchmark.py` escrito; falta Cloudflare y el Mac Mini |
| 1.10 README | primer uso, «cómo crear una colección nueva», benchmark |

Además: `docs/flows.md` con el cuerpo literal de 15 respuestas, `scripts/e2e_local.py`,
`docs/decisions/DECISION_VECTORES_SIN_PGVECTORSTORE.md`.

## Cómo se verificó

- `make check` → ruff `All checks passed!` (81 archivos), pyright `0 errors`, pytest **98 passed, 7 skipped**
  (las 7 de oro se saltan sin API viva). Antes de la auditoría eran 57.
- Rojo a propósito, una vez por pieza (y vuelto a verde):
  - modelo con columna sin migración → `test_modelos_y_migraciones_coinciden` falla (`add_column … columna_fantasma`);
  - detección sin `strip()` → falla el caso «solo espacios»;
  - `merge_peers=True` → falla la página de la cita (`KeyError: 3`): así se encontró el bug de páginas cruzadas;
  - embeddings sin ordenar por `index` → falla el orden de vectores;
  - documento commiteado antes que sus trozos → el test de transacción ve `(1, 0)` en vez de `(0, 0)`;
  - búsqueda sin filtro de `embedding_model` → mezcla modelos; sin umbral → contesta en vez de «no lo sé».
- **Punta a punta real** (`scripts/e2e_local.py`, base desechable, Ollama bge-m3 + llama3.2:3b, 6 documentos del corpus
  incluidos el PDF sin extensión `Informativo INIA N° 91` y el `.txt`):
  `Archivos: 6 · ingeridos: 6 · duplicados: 0 · rechazados: 0 · errores: 0 · trozos: 107` en 206 s;
  preguntas de oro **6 de 7** + la de forma; total ~10 min.
- Latencia de una pregunta con Ollama bge-m3 en el ThinkPad: **0,203 s** (mediana de 10).
- Imagen Docker: 2,03 GB, torch `2.15.0+cpu`, importa Docling y la app.

## Archivos por importancia

1. `app/services/pregunta.py` — `buscar` (filtro por modelo, operador `<=>`), umbral y `_citas_referidas`.
2. `app/services/extraccion.py` — `_trocear`/`_Pieza`: por qué se desactiva `merge_peers` (líneas del docstring).
3. `app/services/ingesta.py` — orden detectar → extraer → embeber → un solo commit; carrera resuelta por la restricción.
4. `app/providers/embeddings.py` — contrato de Cloudflare (docstring), `embeber_*` que traducen fallas de red a 502.
5. `app/models/trozo.py` + `alembic/versions/20261115_1811_4c0ae2807286_*.py` — esquema e índice.
6. `app/providers/llm.py` — selector MiniMax/Ollama y `redactar`.
7. `app/cli/ingestar.py` — resumen con denominador; código 1 solo con errores reales.
8. `tests/conftest.py`, `tests/dobles.py` — dobles de embeddings (bolsa de palabras) y LLM grabador.
9. `docs/flows.md`, `README.md`, `.env.example`, `docker-compose.yml` (`extra_hosts` para Ollama del host).

## Tareas bloqueadas y criterios abiertos

- **1.9**: coseno Ollama vs Cloudflare (falta token y account id) y la medición en el Mac Mini (falta su visto bueno).
- **Criterio 1** (`docker compose up` → respuesta con cita en < 15 min por Swagger): no se migró la base de compose
  porque el permiso de la sesión lo bloqueó. El mismo camino corrió con base desechable.
- **Criterio 3** (oro): falta MiniMax. Con llama3.2:3b falló una: respondió «Сурхондаринская область. [1]», en
  cirílico, copiando el documento. El dato es correcto, pero el test exige el idioma de la pregunta y no se aflojó.
  En otra corrida con la misma temperatura 0 respondió en español: el modelo local no es determinista en Ollama.

## Decisiones tomadas sin Freddy

1. **Sin `PGVectorStore`** (ADR `DECISION_VECTORES_SIN_PGVECTORSTORE.md`): no puede unirse a la transacción del documento.
2. **Cloudflare por su endpoint OpenAI-compatible**: el nativo tiene doc contradictoria (`text` vs `contexts`, sin
   esquema de salida síncrona). Sin probar contra Cloudflare real.
3. **`embedding_model` = `proveedor:modelo`** (`ollama:bge-m3`, `cloudflare:@cf/baai/bge-m3`). Hoy una búsqueda con un
   proveedor no ve lo ingerido con el otro. Si el benchmark 1.9 da coseno > 0,99, se pueden unificar.
4. **Umbral 0,55**: trozos correctos medidos entre 0,24 y 0,51; la pregunta sin respuesta, desde 0,61. Provisional:
   recalibrar con el corpus completo.
5. **`LLM_PROVIDER=ollama`** agregado para pruebas (el default sigue siendo MiniMax). Modelo local `llama3.2:3b`:
   `qwen3:4b` ignora `reasoning=False` y devuelve su razonamiento como respuesta (51 s contra 12,5 s).
6. **Piezas de páginas distintas no se unen** (el `merge_peers` de Docling citaba la página equivocada) y cada trozo
   guarda su rango de páginas (A8).
7. **Texto plano entra como Markdown** a Docling (un solo camino de troceo).
8. PDF sin texto entero → 422 (no se guarda el documento); la FASE_2 lo reingerirá con visión.
9. Respuestas con el formato nativo de FastAPI y errores `{"error": "…"}`; sin envoltorio NestJS (confirmado por la sesión supervisora).

## Corregido tras la auditoría (parte A, 2026-11-16)

Cada punto con un test que falló sin el arreglo (o, donde el rojo inicial fue un import, con una mutación).

| Punto | Arreglo | Test |
|---|---|---|
| A1 | `redactar`: texto vacío del LLM → `ErrorLLM` (502), nunca `sabe=True` | `test_respuesta_vacia_del_llm_es_falla_del_proveedor` |
| A2 | cuerpo no JSON o sin `data`/`index`/`embedding` → `ErrorEmbeddings` (502) | `test_cuerpo_mal_formado_es_error_del_proveedor` (5 casos) |
| A3 | `_nombre_valido`: > 500 o con caracteres de control → 422; vacío → `NOMBRE_ARCHIVO_POR_DEFECTO` | `test_nombre_*`, `test_sin_nombre_usa_el_nombre_por_defecto` |
| A4 | middleware `LimiteDeCuerpo`: 413 por `Content-Length` antes de leer; el chequeo de `detectar` queda de segunda barrera | `tests/test_limite_cuerpo.py` |
| A5 | `ingestar` cierra la transacción de lectura antes de Docling y los embeddings; comentario corregido | `test_no_queda_transaccion_abierta_mientras_se_extrae_y_embebe` |
| A6 | CORS vacío = ningún origen cruzado | `test_sin_origenes_configurados_no_se_permite_ningun_origen_cruzado` |
| A7 | puertos en `127.0.0.1`; `POSTGRES_PASSWORD` con default solo de desarrollo; `.env` opcional para compose | `tests/test_compose.py` (lee `docker compose config`) |
| A8 | rango `pagina_inicio`/`pagina_fin` (migración inicial editada, `CHECK` de rango); prompt «páginas N-M» | `test_rango_de_paginas_de_un_trozo` (4 casos), `test_rango_de_paginas_invertido_se_rechaza` |
| A9 | `DocumentoDuplicado` (la CLI clasifica por tipo, no por 409); versión leída de `pyproject.toml` | `test_clasifica_por_tipo_de_error_y_no_por_codigo`, `tests/test_version.py` |
| A10 | `HTTPStatus` en errores; largos de columna y `LARGO_SHA256_HEX` en `constantes.py`; prefijo del modelo desde el enum | `tests/test_sin_literales.py` (estático) |
| A11 | tipos de retorno en routers y `main.py`; los `type: ignore` explican por qué (firma de Starlette) | `tests/test_tipos_de_retorno.py` (AST) |
| A12 | comentarios de la plantilla reescritos (`database.py`, `settings.py`, `alembic/env.py`, `alembic.ini`) | `tests/test_sin_escombro.py` |
| A13 | `esperar_api` pausa tras cualquier intento fallido; `alembic`/`uvicorn` con `sys.executable -m` | `tests/test_e2e_local.py` |

Cambios de contrato (en `docs/flows.md`, con cuerpos recapturados de la API): la cita pasa de `pagina` a
`pagina_inicio` + `pagina_fin`; nuevos 400 (`Content-Length` inválido), 413 previo a la lectura y 422 por nombre.

## Decisiones de la sesión supervisora (por Freddy, 2026-11-16)

- `catalogo.json` **no** entra como metadatos todavía: queda abierto para Freddy.
- Respuestas en formato nativo de FastAPI, sin envoltorio.
- Un solo commit para FASE_0 + FASE_1. El stage, el sellado, el commit y el push los hace la sesión supervisora;
  la migración de la base de `docker compose` también, después del commit.

## Pendiente para Freddy

1. Términos del plan MiniMax y su llave en uso (criterio 3 y llamada real de la 1.6).
2. Token y account id de Cloudflare, y visto bueno para el Mac Mini (tarea 1.9).
3. `catalogo.json` como fuente del título de las citas.
4. Parte B de la auditoría (B1 a B9), que no bloquea este commit.
