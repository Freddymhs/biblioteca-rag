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

RUN adduser --disabled-password --gecos "" appuser \
    # Carpetas de los volúmenes de compose: un volumen nuevo hereda este dueño.
    && mkdir -p /var/lib/biblioteca-rag/ingesta /home/appuser/.cache \
    && chown -R appuser:appuser /var/lib/biblioteca-rag /home/appuser/.cache
USER appuser

# B6: modelos de Docling y tokenizador dentro de la imagen (un volumen nuevo en
# /home/appuser/.cache hereda este contenido): la primera subida no espera la descarga.
# No toca la base: DATABASE_URL de relleno solo para este paso (los settings la exigen al importar).
RUN DATABASE_URL=sin-base-al-construir python -m app.cli.precargar_modelos

EXPOSE 8000

# B6: Docker (y compose) saben si la API responde, no solo si el proceso vive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# Migra y sirve con un solo proceso (ver docker/arrancar-api.sh). El worker reemplaza el comando.
# En desarrollo: `uv run uvicorn main:app --reload`
CMD ["docker/arrancar-api.sh"]
