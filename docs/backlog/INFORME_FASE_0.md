# Informe FASE_0 — BASE (7/7)

Fecha: 2026-11-15/16 · Sesión asistida por IA, sin Freddy presente.

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 0.1 uv | `pyproject.toml` (proyecto `package = false`), `uv.lock`, `requirements.txt` borrado, `Dockerfile` con `ghcr.io/astral-sh/uv:python3.12-trixie-slim`, `uv sync --locked`, usuario `appuser` |
| 0.2 ruff + pyright | Config en `pyproject.toml`; `make lint`, `make typecheck`, `make test`, `make check` (`Makefile`) |
| 0.3 pgvector | `pgvector/pgvector:pg16`; `psycopg[binary]` 3; `postgresql+psycopg://`; `docker/initdb/01-vector.sql` crea la extensión al iniciar el volumen; proyecto compose `biblioteca-rag`, base `biblioteca_rag` |
| 0.4 Tests reales | `tests/conftest.py`: testcontainers con pgvector, migraciones de Alembic, cada test dentro de una transacción revertida |
| 0.5 Sin `items` | modelo, router, schema, servicio y tests borrados; barrel `app/models/__init__.py` limpio |
| 0.6 `.env.example` | `APP_NAME=biblioteca-rag`, claves vacías de Cloudflare, Ollama y MiniMax |
| 0.7 Escombro | `README.md` y `elevator_speech.md` reescritos (el pitch queda como borrador hasta la FASE_1) |

## Cómo se verificó

- `make check` → ruff `All checks passed!`, pyright `0 errors`, pytest verde.
- Rojo a propósito: lint dio 13 errores sobre el código de plantilla antes de arreglarlo; pyright marcó un
  `x: int = "a"` temporal; con imagen `postgres:16-alpine` el test de pgvector falló con
  `extension "vector" is not available` y volvió a verde con `pgvector/pgvector:pg16`.
- `docker compose up --build` → `/health` = `{"status":"ok","app":"biblioteca-rag"}`, extensión `vector` 0.8.7,
  la API conecta con `postgresql+psycopg`, el proceso corre como `appuser`.

## Archivos por importancia

1. `tests/conftest.py` — el contenedor arranca antes de importar la app (líneas 12-20): settings, engine y
   `alembic/env.py` leen `DATABASE_URL` al importarse.
2. `pyproject.toml` — dependencias, ruff (`known-third-party = ["alembic"]`: la carpeta local confunde a isort), pyright.
3. `Dockerfile` — dos `uv sync` para cachear dependencias aparte del código.
4. `docker-compose.yml` — `DATABASE_URL` del servicio `api` apunta a `db`, no a `localhost`.
5. `.env.example`, `Makefile`, `docker/initdb/01-vector.sql`, `README.md`.

## Decisiones tomadas sin Freddy

- `Makefile` para los scripts `lint`/`typecheck`: uv no tiene task runner y `[project.scripts]` obligaba a empaquetar.
- `pytest.ini` se movió a `pyproject.toml`; se quitó `pytest-asyncio` (ningún test es async).
- Se mantuvo `httpx` para el `TestClient`; queda el aviso de Starlette que pide `httpx2` (el clasificador de permisos
  bloqueó agregarlo como dependencia directa; ya entra como transitiva de `anthropic`).
- Los comentarios de analogías Node (Prisma, Express) en `app/config/database.py` y `alembic/env.py` se dejaron.

## Nota sobre el commit

**Sin commit todavía**: el permiso de la sesión bloqueó `git add` (ver `INFORME_FASE_1.md`). Cuando se selle, el
commit llevará también la FASE_1: comparten `pyproject.toml`, `uv.lock`, `settings.py`,
`errors.py` y `.gitignore` con la FASE_0 y no se pueden separar archivo por archivo sin dejar un commit roto.
El informe de la FASE_1 está en `INFORME_FASE_1.md`.
