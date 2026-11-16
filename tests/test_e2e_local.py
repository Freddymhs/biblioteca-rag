import sys

import pytest

from scripts import e2e_local


def test_espera_entre_intentos_aunque_la_api_responda_otro_codigo() -> None:
    pausas: list[float] = []

    with pytest.raises(RuntimeError):
        e2e_local.esperar_api(lambda: 503, intentos=3, dormir=pausas.append)

    assert len(pausas) == 3


def test_espera_entre_intentos_si_la_api_no_responde() -> None:
    pausas: list[float] = []

    with pytest.raises(RuntimeError):
        e2e_local.esperar_api(lambda: None, intentos=2, dormir=pausas.append)

    assert len(pausas) == 2


def test_termina_en_cuanto_responde_200() -> None:
    respuestas = iter([None, 503, 200])
    pausas: list[float] = []

    e2e_local.esperar_api(lambda: next(respuestas), intentos=5, dormir=pausas.append)

    assert len(pausas) == 2


def test_alembic_y_uvicorn_corren_con_el_mismo_interprete() -> None:
    assert e2e_local.COMANDO_MIGRAR[:3] == [sys.executable, "-m", "alembic"]
    assert e2e_local.COMANDO_API[:3] == [sys.executable, "-m", "uvicorn"]
