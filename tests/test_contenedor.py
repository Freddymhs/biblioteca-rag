"""B6 (contenedor) y B7 (SECRET_KEY sin uso), auditoría FASE_0+1, asignados a la FASE_4."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.config.settings import Settings

RAIZ = Path(__file__).resolve().parent.parent
DOCKERFILE = (RAIZ / "Dockerfile").read_text()
ARRANQUE = RAIZ / "docker" / "arrancar-api.sh"
COMPOSE = yaml.safe_load((RAIZ / "docker-compose.yml").read_text())


def test_b6_la_imagen_declara_un_healthcheck_contra_health() -> None:
    assert re.search(r"^HEALTHCHECK .*\n?.*/health", DOCKERFILE, re.MULTILINE)


def test_b6_la_api_migra_antes_de_servir_y_con_un_solo_proceso() -> None:
    script = ARRANQUE.read_text()

    assert 'CMD ["docker/arrancar-api.sh"]' in DOCKERFILE
    assert os.access(ARRANQUE, os.X_OK)
    assert script.index("alembic upgrade head") < script.index("exec uvicorn")
    assert "--workers 1" in script and "--workers 2" not in DOCKERFILE


def test_b6_los_modelos_se_bajan_al_construir_no_en_la_primera_subida() -> None:
    assert "python -m app.cli.precargar_modelos" in DOCKERFILE
    assert DOCKERFILE.index("USER appuser") < DOCKERFILE.index("precargar_modelos")  # su caché


def test_b6_el_worker_no_hereda_el_healthcheck_http() -> None:
    worker = COMPOSE["services"]["worker"]

    assert worker["healthcheck"] == {"disable": True}
    assert "command" not in COMPOSE["services"]["api"]  # la API usa el CMD que migra


def test_b7_la_app_arranca_sin_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_KEY")  # la fija conftest; aquí se prueba un despliegue sin ella
    ajustes = Settings(_env_file=None, DATABASE_URL="x")  # type: ignore[call-arg]  # sin .env

    assert "SECRET_KEY" not in Settings.model_fields
    assert ajustes.API_KEY.get_secret_value() == ""  # sin clave: lo privado queda cerrado (503)


def test_b7_nadie_menciona_secret_key() -> None:
    rutas = [
        *RAIZ.glob("app/**/*.py"),
        RAIZ / ".env.example",
        RAIZ / "docker-compose.yml",
        RAIZ / "README.md",
    ]
    con_mencion = [
        str(ruta.relative_to(RAIZ)) for ruta in rutas if "SECRET_KEY" in ruta.read_text()
    ]

    assert len(rutas) > 10  # denominador: el barrido vio archivos
    assert con_mencion == []


# ── 4.8: producción (escrita, no ejecutada) ───────────────────────────────────

VARIABLES_PROD = {
    "DOMINIO_PUBLICO": "biblioteca.example.org",
    "API_KEY": "a" * 32,  # G10: la app exige 32 caracteres o más
    "POSTGRES_PASSWORD": "x",
    "APP_DB_PASSWORD": "x",
    "PUBLICO_DB_PASSWORD": "x",
    "CLOUDFLARED_VERSION": "0",
    "CLOUDFLARE_TUNNEL_TOKEN": "x",
    "REDIS_PASSWORD": "x",
}


def _config_prod(variables: dict[str, str]) -> subprocess.CompletedProcess[str]:
    archivos = ["-f", "docker-compose.yml", "-f", "docker-compose.prod.yml"]
    return subprocess.run(
        ["docker", "compose", *archivos, "config", "--format", "json"],
        cwd=RAIZ,
        env={**os.environ, **variables},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(shutil.which("docker") is None, reason="sin docker compose")
def test_48_en_produccion_nada_publica_puertos_y_la_entrada_es_el_tunel() -> None:
    renderizado = _config_prod(VARIABLES_PROD)
    servicios = json.loads(renderizado.stdout)["services"]
    api = servicios["api"]["environment"]

    assert renderizado.returncode == 0, renderizado.stderr
    assert {nombre: s.get("ports", []) for nombre, s in servicios.items()} == dict.fromkeys(
        servicios, []
    )
    assert servicios["cloudflared"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert (api["CONFIAR_EN_CF_CONNECTING_IP"], api["MCP_HOSTS_PERMITIDOS"]) == (
        "true",
        '["biblioteca.example.org"]',
    )


@pytest.mark.skipif(shutil.which("docker") is None, reason="sin docker compose")
@pytest.mark.parametrize(
    "falta",
    ["POSTGRES_PASSWORD", "APP_DB_PASSWORD", "PUBLICO_DB_PASSWORD", "DOMINIO_PUBLICO", "API_KEY"],
)
def test_48_sin_las_variables_de_produccion_no_arranca(falta: str) -> None:
    variables = {**VARIABLES_PROD, falta: ""}

    renderizado = _config_prod(variables)

    assert renderizado.returncode != 0
    assert falta in renderizado.stderr
