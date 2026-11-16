"""Lee docker-compose.yml tal como lo resuelve compose (con interpolación de variables)."""

import json
import os
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SOLO_LOCAL = "127.0.0.1"
MODELOS_HOST = "/usr/share/ollama/.ollama/models"


def _config(*perfiles: str, **variables: str) -> dict:
    opciones = [argumento for perfil in perfiles for argumento in ("--profile", perfil)]
    salida = subprocess.run(
        ["docker", "compose", *opciones, "config", "--format", "json"],
        cwd=RAIZ,
        env={**os.environ, **variables},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(salida.stdout)


def test_puertos_publicados_solo_en_localhost() -> None:
    servicios = _config("ollama")["services"]

    publicados = [
        (nombre, puerto.get("host_ip"))
        for nombre, servicio in servicios.items()
        for puerto in servicio.get("ports", [])
    ]

    assert {nombre for nombre, _ in publicados} == {"api", "db", "redis"}
    assert all(host == SOLO_LOCAL for _, host in publicados), publicados


def test_la_contrasena_de_postgres_sale_de_una_variable() -> None:
    servicios = _config(POSTGRES_PASSWORD="otra-clave")["services"]

    assert servicios["db"]["environment"]["POSTGRES_PASSWORD"] == "otra-clave"
    for nombre in ("api", "worker"):
        assert ":otra-clave@db:" in servicios[nombre]["environment"]["DATABASE_URL"]


def test_api_y_worker_comparten_redis_carpeta_temporal_y_ollama_de_compose() -> None:
    servicios = _config()["services"]
    api, worker = servicios["api"], servicios["worker"]

    for clave in ("REDIS_URL", "INGESTA_TEMPORAL", "OLLAMA_BASE_URL"):
        assert api["environment"][clave] == worker["environment"][clave], clave
    assert api["environment"]["OLLAMA_BASE_URL"] == "http://ollama:11434"
    destinos = {volumen["target"] for volumen in worker["volumes"]}
    assert api["environment"]["INGESTA_TEMPORAL"] in destinos
    assert worker["command"] == ["arq", "app.worker.WorkerSettings"]


def test_ollama_es_opcional_y_puede_usar_los_modelos_del_host_en_solo_lectura() -> None:
    sin_perfil = _config()["services"]
    con_modelos_del_host = _config("ollama", OLLAMA_MODELOS=MODELOS_HOST, OLLAMA_MODELOS_MODO="ro")[
        "services"
    ]["ollama"]

    montaje = con_modelos_del_host["volumes"][0]
    assert "ollama" not in sin_perfil
    assert (montaje["source"], montaje["read_only"]) == (MODELOS_HOST, True)
    assert "ports" not in con_modelos_del_host


def test_redis_persiste_la_cola_al_recrearse() -> None:
    """C11: sin volumen ni AOF, recrear el contenedor perdía las tareas encoladas."""
    redis = _config()["services"]["redis"]

    assert "--appendonly yes" in " ".join(redis["command"])  # D6: va dentro de `sh -c`
    assert "/data" in {volumen["target"] for volumen in redis.get("volumes", [])}
