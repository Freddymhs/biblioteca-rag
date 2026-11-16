"""Prueba de punta a punta con proveedores locales y una base DESECHABLE.

    uv run python scripts/e2e_local.py <carpeta-con-documentos>

Levanta Postgres + pgvector en un contenedor (testcontainers), aplica las migraciones, arranca
la API con Ollama (bge-m3 para embeddings, `OLLAMA_LLM_MODEL` para redactar), crea
`laboral/agricultura`, ingiere la carpeta con la CLI y corre las preguntas de oro contra la API
viva. No toca la base de `docker compose`. Requiere Docker y Ollama con `bge-m3` y el modelo
de LLM descargados.
"""

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from testcontainers.community.postgres import PostgresContainer

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = "8001"
URL = f"http://127.0.0.1:{PUERTO}"
IMAGEN = "pgvector/pgvector:pg16"
INTENTOS_API = 60
PAUSA_ENTRE_INTENTOS_SEGUNDOS = 1.0
# El mismo intérprete que corre este script: no depende de qué `alembic` o `uvicorn` haya en PATH.
COMANDO_MIGRAR = [sys.executable, "-m", "alembic", "upgrade", "head"]
COMANDO_API = [sys.executable, "-m", "uvicorn", "main:app", "--port", PUERTO]


def main() -> int:
    carpeta = sys.argv[1]
    inicio = time.monotonic()

    def marca(texto: str) -> None:
        print(f"[{time.monotonic() - inicio:6.1f}s] {texto}", flush=True)

    with PostgresContainer(IMAGEN, driver="psycopg") as postgres:
        entorno = {
            **os.environ,
            "DATABASE_URL": postgres.get_connection_url(),
            "SECRET_KEY": "e2e-local",
            "EMBEDDINGS_PROVIDER": "ollama",
            "LLM_PROVIDER": "ollama",
        }
        subprocess.run(COMANDO_MIGRAR, cwd=RAIZ, env=entorno, check=True)
        marca("migraciones aplicadas")
        api = subprocess.Popen(COMANDO_API, cwd=RAIZ, env=entorno)
        try:
            esperar_api(_estado_health)
            marca("API arriba")
            httpx.post(f"{URL}/api/espacios", json={"slug": "laboral", "nombre": "Laboral"})
            httpx.post(
                f"{URL}/api/espacios/laboral/colecciones",
                json={"slug": "agricultura", "nombre": "Agricultura"},
            )
            ingesta = subprocess.run(
                [sys.executable, "-m", "app.cli.ingestar", carpeta]
                + ["--espacio", "laboral", "--coleccion", "agricultura"],
                cwd=RAIZ,
                env=entorno,
            )
            marca(f"ingesta terminada (código {ingesta.returncode})")
            oro = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/oro", "-v", "-p", "no:cacheprovider"],
                cwd=RAIZ,
                env={**entorno, "RAG_ORO_URL": URL},
            )
            marca(f"preguntas de oro terminadas (código {oro.returncode})")
        finally:
            api.terminate()
            api.wait(timeout=30)
    return ingesta.returncode or oro.returncode


def esperar_api(
    consultar: Callable[[], int | None],
    intentos: int = INTENTOS_API,
    dormir: Callable[[float], None] = time.sleep,
) -> None:
    """Pausa tras CADA intento fallido: sin respuesta o con un código distinto de 200."""
    for _ in range(intentos):
        if consultar() == httpx.codes.OK:
            return
        dormir(PAUSA_ENTRE_INTENTOS_SEGUNDOS)
    raise RuntimeError(f"La API no respondió 200 en {intentos} intentos")


def _estado_health() -> int | None:
    try:
        return httpx.get(f"{URL}/health").status_code
    except httpx.HTTPError:
        return None


if __name__ == "__main__":
    sys.exit(main())
