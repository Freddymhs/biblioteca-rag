🤖 Proyecto asistido por IA — NO se contabiliza en CV/resume (no es práctica manual real).

# biblioteca-rag

Motor RAG que responde **con cita al documento de origen**, o dice «no lo sé» cuando la respuesta no está en
los datos. Un solo motor, muchas bibliotecas: el dominio es data (espacios y colecciones), no código.
Primer uso: la biblioteca agrícola.

- Concepto: `docs/_CONCEPTO.md` · cambio a servicio público: `docs/decisions/DECISION_SERVICIO_PUBLICO.md`
- Avance: `docs/backlog/README.md`

## Stack

FastAPI · SQLAlchemy 2 + Alembic · Postgres + pgvector · uv · ruff · pyright · pytest + testcontainers.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/)
- Docker con Compose v2 (la base y los tests usan la imagen `pgvector/pgvector:pg16`)

## Primer uso: de cero a una respuesta con cita

```bash
cp .env.example .env
```

En `.env`, elige proveedores:

- **Embeddings**: `CLOUDFLARE_ACCOUNT_ID` y `CLOUDFLARE_API_TOKEN` (por defecto), o local con
  `EMBEDDINGS_PROVIDER=ollama` después de `ollama pull bge-m3`.
- **LLM**: `MINIMAX_API_KEY`, o local con `LLM_PROVIDER=ollama` (`OLLAMA_LLM_MODEL=llama3.2:3b`).
- **Visión** (páginas sin texto): `VISION_PROVIDER=ollama` con `moondream`, o `ninguno`.
- **Claves (FASE_4)**: `API_KEY` (32 caracteres o más; todo `/api` salvo `/api/publico` la exige en `X-API-Key`,
  también para leer), `REDIS_PASSWORD` (`REDIS_URL` fuera de Docker la lleva) y `PUBLICO_DB_PASSWORD` (el usuario
  `biblioteca_web` de lo público, que la API crea al arrancar). Compose no arranca sin ellas. Generar cada una con
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

```bash
docker compose up --build -d                       # api (migra al arrancar), worker, db (pgvector) y redis
```

**Con Ollama dentro de Docker.** El Ollama del host escucha solo en `127.0.0.1` y un contenedor no lo
alcanza (`host.docker.internal` no sirve sin cambiar la configuración del host). Compose trae un
servicio `ollama` opcional, sin puertos publicados, que la API y el worker usan por defecto:

```bash
# Reutilizando los modelos ya bajados en el host, en solo lectura (no baja nada):
export OLLAMA_MODELOS=/usr/share/ollama/.ollama/models OLLAMA_MODELOS_MODO=ro
docker compose --profile ollama up --build -d

# O con su propio volumen, bajando los modelos una vez:
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull bge-m3
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull moondream
```

La imagen de `ollama` está fijada a la versión del host (0.34.0): las más nuevas migran el formato de
los manifiestos al arrancar y fallan con los modelos montados en solo lectura. Probado de punta a punta
el 2026-11-16: subir un PDF del corpus, lote por el worker y pregunta con cita, todo dentro de Docker.

API en `http://localhost:8000` · Swagger en `http://localhost:8000/docs` · Postgres en `localhost:5432` ·
Redis en `localhost:6379` (todos solo en `127.0.0.1`). La extensión `vector` se crea al inicializar el
volumen (`docker/initdb/`). Los modelos de layout y tablas de Docling y el tokenizador de bge-m3 vienen dentro
de la imagen (`app.cli.precargar_modelos` al construir): la primera subida no espera la descarga.

En Swagger (botón **Authorize** con la `API_KEY`), en este orden: `POST /api/espacios` → `POST /api/espacios/{espacio}/colecciones` →
`POST …/documentos` (sube un PDF o `.txt`) → `POST /api/preguntas`. Detalle de cada cuerpo en `docs/flows.md`.

## Cómo crear una colección nueva

El dominio es data: una colección nueva no toca código.

1. Elige el **espacio** (área de vida: `intereses`, `personal`, `estudios`). Si no existe:
   ```bash
   export CLAVE="X-API-Key: $(grep ^API_KEY= .env | cut -d= -f2-)"   # todo /api privado la pide
   curl -X POST localhost:8000/api/espacios -H "$CLAVE" -H 'Content-Type: application/json' \
     -d '{"slug": "intereses", "nombre": "Intereses"}'
   ```
2. Crea la **colección** dentro del espacio (slug en minúsculas, dígitos y guiones):
   ```bash
   curl -X POST localhost:8000/api/espacios/intereses/colecciones -H "$CLAVE" -H 'Content-Type: application/json' \
     -d '{"slug": "agricultura", "nombre": "Agricultura"}'
   ```
3. Carga documentos, uno por la API o una carpeta entera por la CLI:
   ```bash
   curl -X POST localhost:8000/api/espacios/intereses/colecciones/agricultura/documentos -H "$CLAVE" \
     -F 'archivo=@manual.pdf'

   uv run python -m app.cli.ingestar /ruta/a/la/carpeta --espacio intereses --coleccion agricultura \
     --excluir catalogo.json --excluir prompt.txt --excluir LIBROS_POR_REBUSCAR.md
   ```
   Con la API, hasta 10 MB y 30 páginas; lo más pesado va como **lote** (413 si no). El tipo se detecta por contenido (un PDF sin extensión entra igual). El mismo archivo dos veces
   no duplica trozos (409). Las páginas sin texto pasan por el modelo de visión (las en blanco se
   descartan). Para muchos archivos sin bloquear la API, súbelos como **lote**: el worker los procesa
   y el avance se consulta en `GET /api/trabajos/{id}`:
   ```bash
   curl -X POST localhost:8000/api/espacios/intereses/colecciones/agricultura/lotes -H "$CLAVE" \
     -F 'archivos=@uno.pdf' -F 'archivos=@dos.pdf'
   ```
4. Pregunta acotada a la colección, o a todo el espacio omitiendo `coleccion`:
   ```bash
   curl -X POST localhost:8000/api/preguntas -H "$CLAVE" -H 'Content-Type: application/json' \
     -d '{"pregunta": "¿Cuál es el Kc del olivo?", "espacio": "intereses", "coleccion": "agricultura"}'
   ```
5. Escribe sus **preguntas de oro** (`tests/oro/<coleccion>.json`, con al menos una sin respuesta) y
   córrelas contra la API viva: `RAG_ORO_URL=http://localhost:8000 RAG_ORO_API_KEY=... uv run pytest tests/oro -v`.

## Servicio público y MCP

Sin clave, solo lectura y solo lo público: colecciones marcadas `publica` y, dentro, documentos con licencia
**verificada por una persona** (rol de Postgres `biblioteca_publico` con RLS: Postgres filtra, no el código).

```bash
curl -X PATCH localhost:8000/api/espacios/intereses/colecciones/agricultura -H "$CLAVE" \
  -H 'Content-Type: application/json' -d '{"publica": true}'
curl -X PUT localhost:8000/api/espacios/intereses/colecciones/agricultura/documentos/1/licencia -H "$CLAVE" \
  -H 'Content-Type: application/json' -d '{"licencia": "CC BY 4.0", "verificada": true}'

curl 'localhost:8000/api/publico/buscar?q=Kc%20del%20olivo'     # fragmentos con cita, sin LLM
curl -X POST localhost:8000/api/publico/preguntas -H 'Content-Type: application/json' \
  -d '{"pregunta": "¿Cuál es el Kc del olivo?"}'                 # redactada: límite más bajo
```

Al reconstruir la base desde cero y volver a ingerir, repite esos dos pasos (colección pública y licencia verificada): las migraciones corren sobre la base vacía, antes de la ingesta.

Límites por IP y tope diario de respuestas (429 al pasarlos) en `.env`. MCP por HTTP en `http://localhost:8000/mcp`
(tools `buscar` y `preguntar`, de solo lectura); un agente lo agrega como servidor MCP «streamable HTTP». Las
licencias del corpus están en `docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md` (el veredicto es de Freddy) y la
exposición a internet, escrita y sin ejecutar, en `docs/DESPLIEGUE_PUBLICO.md`.

## Desarrollo local

```bash
cp .env.example .env
uv sync                                  # crea .venv con dependencias y grupo dev
docker compose up -d db                  # solo la base
uv run alembic upgrade head              # aplica migraciones
uv run python -m app.cli.usuario_publico  # usuario de lo público (DATABASE_URL_PUBLICA en .env)
uv run uvicorn main:app --reload
```

## Calidad

```bash
make lint        # ruff check + ruff format --check
make typecheck   # pyright
make test        # pytest contra Postgres + pgvector real (testcontainers, necesita Docker)
make check       # los tres
```

Los tests levantan un contenedor desechable, aplican las migraciones de Alembic y revierten cada test
dentro de una transacción. No tocan la base de `docker compose`.

## Migraciones

```bash
uv run alembic revision --autogenerate -m "describe el cambio"
uv run alembic upgrade head
```

Todo modelo nuevo se importa en `app/models/__init__.py`; si no, autogenerate no lo ve (`CLAUDE.md`).

## Paquetes de dominio (datos estructurados y cálculos)

Una colección puede declarar un paquete (`"paquete": "facturas"` al crearla). Sus documentos no se
embeben al subirlos: el LLM propone los datos con el esquema del paquete y una persona los confirma.

```bash
curl -X POST localhost:8000/api/espacios/intereses/colecciones -H "$CLAVE" -H 'Content-Type: application/json' \
  -d '{"slug": "facturas", "nombre": "Facturas", "paquete": "facturas"}'
curl -X POST localhost:8000/api/espacios/intereses/colecciones/facturas/documentos -H "$CLAVE" -F 'archivo=@factura.pdf'
curl localhost:8000/api/extracciones/1/formulario -H "$CLAVE"            # JSON Schema + propuesta del LLM
curl -X POST localhost:8000/api/extracciones/1/confirmacion -H "$CLAVE" -H 'Content-Type: application/json' \
  -d @factura-corregida.json                                   # recién aquí queda buscable
curl -X PUT localhost:8000/api/extracciones/1/confirmacion -H "$CLAVE" -H 'Content-Type: application/json' \
  -d @factura-corregida.json                                   # corrige una ya confirmada
curl -X POST localhost:8000/api/extracciones/2/rechazo -H "$CLAVE"         # descarta una pendiente y su documento
```

Al preguntar en esa colección, un cálculo («¿cuánto facturé en marzo?») va a una herramienta SQL fija
del paquete y un significado, a la búsqueda semántica. El LLM nunca escribe SQL: elige una
herramienta de una lista cerrada y propone argumentos que se validan. Un paquete nuevo es un módulo
en `app/dominio/` (esquema, texto a embeber, herramientas) y una entrada en `app/dominio/__init__.py`.

## Observabilidad

```bash
# En .env: TRAZAS_OTLP_URL=http://jaeger:4318/v1/traces
docker compose --profile trazas up -d               # Jaeger local, UI en http://127.0.0.1:16686
curl -i localhost:8000/api/publico/buscar?q=riego    # el encabezado X-Traza-Id abre la traza en Jaeger
curl localhost:8000/api/uso?dias=7 -H "$CLAVE"       # consultas públicas y 429 por día (privado)
```

Cada traza muestra las etapas (embeber, buscar, redactar; clasificar y calcular en un paquete) con su latencia,
los trozos candidatos y usados y el proveedor. No guarda el texto de las preguntas ni IPs. Detalle en
`docs/flows.md` («Observabilidad»).

## Mantenimiento de colecciones

```bash
uv run python -m app.cli.reembeber --espacio intereses --coleccion agricultura   # cambio de modelo
uv run python -m app.cli.reembeber --espacio intereses --retrocear                # cambio de troceo (no a las con paquete)
uv run python -m app.cli.sincronizar --espacio personal --coleccion sobre-mi --conector resume
uv run python scripts/medir_hnsw.py        # búsqueda con filtros e índice HNSW (ver docs/decisions/)
```

## Benchmark de embeddings

```bash
uv run python scripts/benchmark.py              # Ollama vs Cloudflare: coseno > 0,99 y pregunta < 1 s
uv run python scripts/benchmark.py --solo-ollama
```

## Estructura

```
main.py              # app, middleware, routers (privados con API key, /api/publico) y MCP en /mcp
app/mcp_publico.py   # MCP público: tools buscar y preguntar (solo lectura)
app/worker.py        # worker de arq: ingesta y sincronización en segundo plano
alembic/             # migraciones
app/
├── config/          # settings (env validado) y database (engine del dueño y engine público)
├── common/          # errores de dominio, logger y API key
├── models/          # tablas SQLAlchemy
├── schemas/         # contratos Pydantic de request/response
├── services/        # detección, extracción, ingesta, pregunta, catálogo
├── providers/       # embeddings y LLM tras interfaces de LangChain; cola y límite de uso (Redis)
├── cli/             # ingesta de carpetas, re-embed, sincronización, usuario público, precarga de modelos
├── conectores/      # fuentes externas (API de resume)
└── routers/         # rutas HTTP
docker/initdb/       # SQL que corre al crear el volumen de Postgres
docker/arrancar-api.sh # migra y sirve (CMD de la imagen)
docker-compose.prod.yml # producción tras Cloudflare Tunnel (escrito, sin ejecutar: docs/DESPLIEGUE_PUBLICO.md)
scripts/benchmark.py # tarea 1.9
tests/               # oro/: preguntas de oro contra la API viva
```
