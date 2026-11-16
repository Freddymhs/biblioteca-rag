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
- Con Ollama corriendo en el host y la API en Docker: `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head      # crea las tablas (una vez)
```

API en `http://localhost:8000` · Swagger en `http://localhost:8000/docs` · Postgres en `localhost:5432`.
La extensión `vector` se crea al inicializar el volumen (`docker/initdb/`). La primera ingesta descarga
los modelos de layout y tablas de Docling y el tokenizador de bge-m3 (cientos de MB, una vez).

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
   no duplica trozos (409). Un PDF sin capa de texto se rechaza y sus páginas quedan en el log.
   Para carpetas grandes corre la CLI dentro del contenedor (`docker compose exec api python -m
   app.cli.ingestar /datos/... `, montando la carpeta): Docling con PDFs pesados usa varios GB de RAM.
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

## Benchmark de embeddings

```bash
uv run python scripts/benchmark.py              # Ollama vs Cloudflare: coseno > 0,99 y pregunta < 1 s
uv run python scripts/benchmark.py --solo-ollama
```

## Estructura

```
main.py              # app, middleware, routers
alembic/             # migraciones
app/
├── config/          # settings (env validado) y database (engine, sesión, Base)
├── common/          # errores de dominio y logger
├── models/          # tablas SQLAlchemy
├── schemas/         # contratos Pydantic de request/response
├── services/        # detección, extracción, ingesta, pregunta, catálogo
├── providers/       # embeddings y LLM tras interfaces de LangChain
├── cli/             # ingesta de carpetas
└── routers/         # rutas HTTP
docker/initdb/       # SQL que corre al crear el volumen de Postgres
scripts/benchmark.py # tarea 1.9
tests/               # oro/: preguntas de oro contra la API viva
```
