"""Lee docker-compose.yml tal como lo resuelve compose (con interpolación de variables)."""

import json
import os
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SOLO_LOCAL = "127.0.0.1"


def _config(**variables: str) -> dict:
    salida = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=RAIZ,
        env={**os.environ, **variables},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(salida.stdout)


def test_puertos_publicados_solo_en_localhost() -> None:
    servicios = _config()["services"]

    publicados = [
        (nombre, puerto.get("host_ip"))
        for nombre, servicio in servicios.items()
        for puerto in servicio.get("ports", [])
    ]

    assert len(publicados) == 2
    assert all(host == SOLO_LOCAL for _, host in publicados), publicados


def test_la_contrasena_de_postgres_sale_de_una_variable() -> None:
    servicios = _config(POSTGRES_PASSWORD="otra-clave")["services"]

    assert servicios["db"]["environment"]["POSTGRES_PASSWORD"] == "otra-clave"
    assert ":otra-clave@db:" in servicios["api"]["environment"]["DATABASE_URL"]
