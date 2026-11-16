# FASE 0: BASE — adaptar la plantilla al concepto

**Prioridad**: Alta · **Dependencias**: —

## Orden de ejecución

1. Tarea 0.1 — pyproject que las demás usan.
2. Tarea 0.3 — driver y base que 0.4 necesita.
3. Tarea 0.4 — depende de 0.3. Resto independiente.

## Tareas

- [x] **0.1 uv**: crear `pyproject.toml`, borrar `requirements.txt`, `Dockerfile` instala con uv.
- [x] **0.2 ruff + pyright** en `pyproject.toml`; scripts `lint` y `typecheck`.
- [x] **0.3 Postgres con vectores**: `docker-compose.yml` → `pgvector/pgvector:pg16`; `psycopg[binary]` 3 (lo exige `langchain-postgres`); `DATABASE_URL` `postgresql+psycopg://`.
- [x] **0.4 Tests contra base real**: `tests/conftest.py` con testcontainers (pgvector), sin SQLite.
- [x] **0.5 Sacar ejemplo `items`**: `app/{models,routers,schemas,services}/item*.py`, `tests/test_items.py`.
- [x] **0.6 `.env.example`**: `APP_NAME=biblioteca-rag`; claves vacías de Cloudflare, MiniMax, Ollama.
- [x] **0.7 Escombro de plantilla**: `README.md` y `elevator_speech.md` describen template-fastapi.

## Criterios de Aceptación

- [x] `uv run pytest` verde contra pgvector real.
- [x] ruff y pyright con 0 errores.
- [x] `docker compose up` levanta API + base con la extensión `vector`.
