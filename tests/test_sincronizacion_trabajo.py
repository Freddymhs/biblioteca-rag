"""La sincronización como trabajo en segundo plano: endpoint (202) + worker con conector doble."""

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.conectores.base import ErrorConector, Registro
from app.config.constantes import FUNCION_SINCRONIZAR
from app.config.settings import settings
from app.providers.cola import obtener_cola
from app.services import catalogo
from app.services.trabajos import id_tarea_sincronizacion
from app.worker import procesar_sincronizacion
from main import app
from tests.dobles import ColaDoble, proveedor_doble

URL = "/api/espacios/personal/colecciones/sobre-mi/sincronizaciones"
REGISTROS = [
    Registro("work:SIIGSA", "resume: work", "Sección: work\nsummary: Riego del olivo"),
    Registro("skills:Backend", "resume: skills", "Sección: skills\nkeywords: Python"),
]


@pytest.fixture
def cola(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> ColaDoble:
    monkeypatch.setattr(settings, "RESUME_API_URL", "http://resume.local")
    catalogo.crear_espacio(db, "personal", "Personal")
    catalogo.crear_coleccion(db, "personal", "sobre-mi", "Sobre mí")
    doble = ColaDoble()
    app.dependency_overrides[obtener_cola] = lambda: doble
    return doble


def _procesar(db: Session, cola: ColaDoble, crear_conector_) -> None:
    @contextmanager
    def sesion() -> Generator[Session, None, None]:
        yield db

    for _funcion, (trabajo_id, conector, permitir_vaciar) in cola.encolados:
        procesar_sincronizacion(
            sesion, proveedor_doble, crear_conector_, trabajo_id, conector, permitir_vaciar
        )


class ConectorDoble:
    nombre = "resume"

    def __init__(self, caido: bool = False) -> None:
        self.caido = caido

    def registros(self) -> list[Registro]:
        if self.caido:
            raise ErrorConector("La API de resume no respondió")
        return REGISTROS


def test_sincronizacion_encolada_y_procesada(
    client: TestClient, cola: ColaDoble, db: Session
) -> None:
    respuesta = client.post(URL, json={"conector": "resume"})

    cuerpo = respuesta.json()
    assert respuesta.status_code == 202
    assert (cuerpo["tipo"], cuerpo["estado"], cuerpo["total"]) == (
        "sincronizacion",
        "pendiente",
        None,
    )
    assert cola.encolados == [(FUNCION_SINCRONIZAR, (cuerpo["id"], "resume", False))]
    assert cola.ids_de_tarea == [id_tarea_sincronizacion(cuerpo["id"])]

    _procesar(db, cola, lambda _nombre: ConectorDoble())

    final = client.get(f"/api/trabajos/{cuerpo['id']}").json()
    assert (final["estado"], final["total"], final["ingeridos"]) == ("terminado", 2, 2)


def test_fuente_caida_termina_el_trabajo_con_el_motivo(
    client: TestClient, cola: ColaDoble, db: Session
) -> None:
    trabajo_id = client.post(URL, json={"conector": "resume"}).json()["id"]

    _procesar(db, cola, lambda _nombre: ConectorDoble(caido=True))

    final = client.get(f"/api/trabajos/{trabajo_id}").json()
    assert (final["estado"], final["errores"]) == ("terminado", 1)
    assert final["ultimo_error"] == "La API de resume no respondió"


def test_conector_desconocido_es_422_y_sin_configurar_es_503(
    client: TestClient, cola: ColaDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    desconocido = client.post(URL, json={"conector": "no-existe"})
    monkeypatch.setattr(settings, "RESUME_API_URL", "")
    sin_configurar = client.post(URL, json={"conector": "resume"})

    assert desconocido.status_code == 422
    assert sin_configurar.status_code == 503
    assert cola.encolados == []
