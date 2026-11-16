FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

WORKDIR /app

# Copia desde la caché en vez de enlazar; omite el grupo dev; compila bytecode al instalar.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Dependencias primero (capa cacheada: solo se reconstruye si cambia uv.lock o pyproject.toml)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

# Producción con 2 workers. En desarrollo: `uv run uvicorn main:app --reload`
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
