"""D6 (auditoría FASE_2): Redis exige contraseña; la cola y el límite de uso la usan."""

import asyncio
import secrets
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from redis import Redis
from testcontainers.redis import RedisContainer

from app.common.errors import AppError
from app.config.constantes import UsoPublico
from app.providers.cola import ColaArq
from app.providers.limites import Limitador

COMPOSE = Path(__file__).resolve().parent.parent / "docker-compose.yml"
CLAVE = secrets.token_urlsafe(16)


@pytest.fixture(scope="module")
def redis_con_clave() -> Generator[tuple[str, str], None, None]:
    """(url con contraseña, url sin ella) del mismo Redis con `requirepass`."""
    with RedisContainer("redis:7-alpine", password=CLAVE) as redis:
        anfitrion = f"{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}"
        yield f"redis://:{CLAVE}@{anfitrion}", f"redis://{anfitrion}"


def test_el_limite_de_uso_entra_con_la_clave_y_sin_ella_no(
    redis_con_clave: tuple[str, str],
) -> None:
    con_clave, sin_clave = redis_con_clave

    Limitador(Redis.from_url(con_clave)).consumir(UsoPublico.BUSQUEDA, "1.1.1.1")
    with pytest.raises(AppError) as error:
        Limitador(Redis.from_url(sin_clave)).consumir(UsoPublico.BUSQUEDA, "1.1.1.1")

    assert error.value.status_code == 503


def test_la_cola_entra_con_la_clave_y_sin_ella_no(redis_con_clave: tuple[str, str]) -> None:
    con_clave, sin_clave = redis_con_clave

    asyncio.run(ColaArq(con_clave).verificar())
    with pytest.raises(AppError) as error:
        asyncio.run(ColaArq(sin_clave).verificar())

    assert error.value.status_code == 503


def test_el_compose_no_levanta_redis_sin_contrasena() -> None:
    compose = yaml.safe_load(COMPOSE.read_text())
    redis = compose["services"]["redis"]
    url_de_la_app = compose["x-app"]["environment"]["REDIS_URL"]

    assert "--requirepass" in " ".join(redis["command"])
    assert "REDIS_PASSWORD:?" in redis["environment"]["REDIS_PASSWORD"]  # sin valor, no arranca
    assert url_de_la_app.startswith("redis://:${REDIS_PASSWORD:?")
    assert "REDISCLI_AUTH" in " ".join(redis["healthcheck"]["test"])
