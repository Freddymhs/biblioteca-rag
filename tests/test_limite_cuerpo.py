from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.common.limite_cuerpo import LimiteDeCuerpo
from app.config.constantes import MARGEN_MULTIPART_BYTES, MAX_BYTES_SUBIDA

LIMITE_DE_PRUEBA = 10


def _app_de_prueba() -> tuple[FastAPI, list[bytes]]:
    leidos: list[bytes] = []
    app = FastAPI()
    app.add_middleware(LimiteDeCuerpo, max_bytes=LIMITE_DE_PRUEBA)

    @app.post("/eco")
    async def eco(request: Request) -> dict[str, int]:
        leidos.append(await request.body())
        return {"bytes": len(leidos[-1])}

    return app, leidos


def test_rechaza_por_content_length_sin_leer_el_cuerpo() -> None:
    app, leidos = _app_de_prueba()

    respuesta = TestClient(app).post("/eco", content=b"x" * (LIMITE_DE_PRUEBA + 1))

    assert respuesta.status_code == 413
    assert "error" in respuesta.json()
    assert leidos == []  # el endpoint nunca corrió


def test_deja_pasar_lo_que_cabe() -> None:
    app, leidos = _app_de_prueba()

    respuesta = TestClient(app).post("/eco", content=b"x" * LIMITE_DE_PRUEBA)

    assert respuesta.status_code == 200
    assert leidos == [b"x" * LIMITE_DE_PRUEBA]


def test_content_length_invalido_es_400() -> None:
    app, _ = _app_de_prueba()

    respuesta = TestClient(app).post("/eco", content=b"x", headers={"content-length": "abc"})

    assert respuesta.status_code == 400


def test_la_app_real_lo_tiene_con_el_maximo_de_subida() -> None:
    from main import app

    limites = [m.kwargs["max_bytes"] for m in app.user_middleware if m.cls is LimiteDeCuerpo]

    assert limites == [MAX_BYTES_SUBIDA + MARGEN_MULTIPART_BYTES]
