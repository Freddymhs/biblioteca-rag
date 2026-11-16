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

```bash
docker compose up --build -d                       # api, worker, db (pgvector) y redis
docker compose exec api alembic upgrade head      # crea o actualiza las tablas
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
volumen (`docker/initdb/`). La primera ingesta descarga los modelos de layout y tablas de Docling y el
tokenizador de bge-m3 al volumen `modelos_hf` (cientos de MB, una vez, compartido por api y worker).

En Swagger, en este orden: `POST /api/espacios` → `POST /api/espacios/{espacio}/colecciones` →
`POST …/documentos` (sube un PDF o `.txt`) → `POST /api/preguntas`. Detalle de cada cuerpo en `docs/flows.md`.

## Cómo crear una colección nueva

El dominio es data: una colección nueva no toca código.

1. Elige el **espacio** (área de vida: `laboral`, `personal`, `estudios`). Si no existe:
   ```bash
   curl -X POST localhost:8000/api/espacios -H 'Content-Type: application/json' \
     -d '{"slug": "laboral", "nombre": "Laboral"}'
   ```
2. Crea la **colección** dentro del espacio (slug en minúsculas, dígitos y guiones):
   ```bash
   curl -X POST localhost:8000/api/espacios/laboral/colecciones -H 'Content-Type: application/json' \
     -d '{"slug": "agricultura", "nombre": "Agricultura"}'
   ```
3. Carga documentos, uno por la API o una carpeta entera por la CLI:
   ```bash
   curl -X POST localhost:8000/api/espacios/laboral/colecciones/agricultura/documentos \
     -F 'archivo=@manual.pdf'

   uv run python -m app.cli.ingestar /ruta/a/la/carpeta --espacio laboral --coleccion agricultura \
     --excluir catalogo.json --excluir prompt.txt --excluir LIBROS_POR_REBUSCAR.md
   ```
   El tipo se detecta por contenido (un PDF sin extensión entra igual). El mismo archivo dos veces
   no duplica trozos (409). Las páginas sin texto pasan por el modelo de visión (las en blanco se
   descartan). Para muchos archivos sin bloquear la API, súbelos como **lote**: el worker los procesa
   y el avance se consulta en `GET /api/trabajos/{id}`:
   ```bash
   curl -X POST localhost:8000/api/espacios/laboral/colecciones/agricultura/lotes \
     -F 'archivos=@uno.pdf' -F 'archivos=@dos.pdf'
   ```
4. Pregunta acotada a la colección, o a todo el espacio omitiendo `coleccion`:
   ```bash
   curl -X POST localhost:8000/api/preguntas -H 'Content-Type: application/json' \
     -d '{"pregunta": "¿Cuál es el Kc del olivo?", "espacio": "laboral", "coleccion": "agricultura"}'
   ```
5. Escribe sus **preguntas de oro** (`tests/oro/<coleccion>.json`, con al menos una sin respuesta) y
   córrelas contra la API viva: `RAG_ORO_URL=http://localhost:8000 uv run pytest tests/oro -v`.

## Desarrollo local

```bash
cp .env.example .env
uv sync                                  # crea .venv con dependencias y grupo dev
docker compose up -d db                  # solo la base
uv run alembic upgrade head              # aplica migraciones
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

## Mantenimiento de colecciones

```bash
uv run python -m app.cli.reembeber --espacio laboral --coleccion agricultura   # cambio de modelo
uv run python -m app.cli.reembeber --espacio laboral --retrocear                # cambio de troceo
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
main.py              # app, middleware, routers
app/worker.py        # worker de arq: ingesta y sincronización en segundo plano
alembic/             # migraciones
app/
├── config/          # settings (env validado) y database (engine, sesión, Base)
├── common/          # errores de dominio y logger
├── models/          # tablas SQLAlchemy
├── schemas/         # contratos Pydantic de request/response
├── services/        # detección, extracción, ingesta, pregunta, catálogo
├── providers/       # embeddings y LLM tras interfaces de LangChain
├── cli/             # ingesta de carpetas, re-embed, sincronización
├── conectores/      # fuentes externas (API de resume)
└── routers/         # rutas HTTP
docker/initdb/       # SQL que corre al crear el volumen de Postgres
scripts/benchmark.py # tarea 1.9
tests/               # oro/: preguntas de oro contra la API viva
```
