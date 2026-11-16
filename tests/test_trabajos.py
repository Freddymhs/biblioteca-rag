from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.errors import service_unavailable
from app.common.limite_cuerpo import LimiteDeCuerpo
from app.config.constantes import FUNCION_INGESTAR, MAX_BYTES_LOTE, PATRON_RUTA_LOTES
from app.config.settings import settings
from app.providers.cola import obtener_cola
from app.services import catalogo
from app.worker import procesar_archivo
from main import app
from tests.dobles import ColaDoble, LLMGrabador, RespuestaHTTP, proveedor_doble
from tests.pdf_minimo import pdf_minimo

URL_LOTES = "/api/espacios/laboral/colecciones/agricultura/lotes"
PDF = pdf_minimo(["Riego del olivo\nEl Kc del olivo es 0.65."])


@pytest.fixture
def cola(client: TestClient) -> ColaDoble:
    doble = ColaDoble()
    app.dependency_overrides[obtener_cola] = lambda: doble
    return doble


@pytest.fixture(autouse=True)
def entorno(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "INGESTA_TEMPORAL", tmp_path / "ingesta")
    catalogo.crear_espacio(db, "laboral", "Laboral")
    catalogo.crear_coleccion(db, "laboral", "agricultura", "Agricultura")


def _subir_lote(client: TestClient) -> RespuestaHTTP:
    archivos = [
        ("archivos", ("olivo.pdf", PDF)),
        ("archivos", ("copia-del-olivo.pdf", PDF)),
        ("archivos", ("vacio.pdf", b"")),
    ]
    return client.post(URL_LOTES, files=archivos)


def _procesar_cola(db: Session, cola: ColaDoble, obtener_proveedor=proveedor_doble) -> None:
    """Hace lo que haría el worker con cada trabajo encolado, en la sesión del test."""

    @contextmanager
    def sesion() -> Generator[Session, None, None]:
        yield db

    for _funcion, (trabajo_id, ruta, nombre) in cola.encolados:
        procesar_archivo(sesion, obtener_proveedor, lambda: None, trabajo_id, Path(ruta), nombre)


def test_subir_lote_responde_202_sin_procesar_y_encola_un_trabajo_por_archivo(
    client: TestClient, cola: ColaDoble
) -> None:
    respuesta = _subir_lote(client)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 202
    assert (cuerpo["estado"], cuerpo["total"], cuerpo["procesados"]) == ("pendiente", 3, 0)
    assert [funcion for funcion, _ in cola.encolados] == [FUNCION_INGESTAR] * 3
    nombres = [argumentos[2] for _, argumentos in cola.encolados]
    assert nombres == ["olivo.pdf", "copia-del-olivo.pdf", "vacio.pdf"]
    assert Path(cola.encolados[0][1][1]).read_bytes() == PDF  # la copia que leerá el worker


def test_el_avance_se_consulta_y_el_worker_limpia_las_copias(
    client: TestClient, cola: ColaDoble, db: Session
) -> None:
    trabajo_id = _subir_lote(client).json()["id"]
    carpeta = settings.INGESTA_TEMPORAL / str(trabajo_id)

    _procesar_cola(db, cola)

    cuerpo = client.get(f"/api/trabajos/{trabajo_id}").json()
    assert cuerpo["estado"] == "terminado"
    contadores = (
        cuerpo["ingeridos"],
        cuerpo["duplicados"],
        cuerpo["rechazados"],
        cuerpo["errores"],
    )
    assert contadores == (1, 1, 1, 0)
    assert cuerpo["procesados"] == cuerpo["total"] == 3
    assert "vacío" in cuerpo["ultimo_error"]
    assert not carpeta.exists()


def test_proveedor_sin_configurar_cuenta_como_error_con_su_motivo(
    client: TestClient, cola: ColaDoble, db: Session
) -> None:
    trabajo_id = _subir_lote(client).json()["id"]

    def proveedor_sin_credenciales():
        raise service_unavailable("Embeddings sin configurar")

    _procesar_cola(db, cola, proveedor_sin_credenciales)

    cuerpo = client.get(f"/api/trabajos/{trabajo_id}").json()
    assert (cuerpo["errores"], cuerpo["estado"]) == (3, "terminado")
    assert cuerpo["ultimo_error"] == "Embeddings sin configurar"


def test_sin_cola_responde_503_y_no_deja_trabajo_ni_copias(client: TestClient, db: Session) -> None:
    from app.models import Trabajo

    app.dependency_overrides[obtener_cola] = lambda: ColaDoble(caida=True)

    respuesta = _subir_lote(client)

    assert respuesta.status_code == 503
    assert db.query(Trabajo).count() == 0
    assert not settings.INGESTA_TEMPORAL.exists()  # ni siquiera se empezó a copiar


def test_trabajo_inexistente_es_404(client: TestClient) -> None:
    assert client.get("/api/trabajos/999999").status_code == 404


def test_los_lotes_tienen_su_propio_limite_de_cuerpo() -> None:
    limite = LimiteDeCuerpo(app, max_bytes=10, limites_por_ruta={PATRON_RUTA_LOTES: 100})

    assert limite._limite("/api/espacios/laboral/colecciones/agricultura/lotes") == 100
    assert limite._limite("/api/espacios/laboral/colecciones/agricultura/documentos") == 10
    reales = [m.kwargs for m in app.user_middleware if m.cls is LimiteDeCuerpo]
    limites = reales[0]["limites_por_ruta"]
    assert isinstance(limites, dict) and limites[PATRON_RUTA_LOTES] == MAX_BYTES_LOTE


def test_la_vision_del_worker_se_usa(client: TestClient, cola: ColaDoble, db: Session) -> None:
    """El worker recibe la visión por fábrica: una página con figura se indexa también ahí."""
    from tests.pdf_minimo import FIGURA

    client.post(URL_LOTES, files=[("archivos", ("figura.pdf", pdf_minimo([FIGURA])))])
    _funcion, (trabajo_id, ruta, nombre) = cola.encolados[0]

    @contextmanager
    def sesion() -> Generator[Session, None, None]:
        yield db

    vision = LLMGrabador(respuesta="Grafico de potasio")
    archivo = procesar_archivo(
        sesion, proveedor_doble, lambda: vision, trabajo_id, Path(ruta), nombre
    )

    assert (archivo.resultado.value, archivo.trozos) == ("ingeridos", 1)


# ── C5: tope real de bytes al copiar (aunque no venga Content-Length) ────────


@pytest.mark.parametrize(
    ("tope_archivo", "tope_lote"),
    [(len(PDF) - 1, 10 * len(PDF)), (10 * len(PDF), len(PDF) + 1)],
    ids=["archivo-grande", "lote-grande"],
)
def test_lote_que_supera_el_tope_al_copiar_es_413_y_no_deja_nada(
    client: TestClient,
    cola: ColaDoble,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tope_archivo: int,
    tope_lote: int,
) -> None:
    from app.models import Trabajo

    monkeypatch.setattr("app.routers.trabajos.MAX_BYTES_SUBIDA", tope_archivo)
    monkeypatch.setattr("app.routers.trabajos.MAX_BYTES_LOTE", tope_lote)

    respuesta = _subir_lote(client)

    assert respuesta.status_code == 413
    assert db.query(Trabajo).count() == 0
    assert cola.encolados == []
    assert not settings.INGESTA_TEMPORAL.exists() or not any(settings.INGESTA_TEMPORAL.iterdir())


# ── C6: ningún trabajo «pendiente» eterno ───────────────────────────────────


def test_si_la_cola_no_responde_no_se_crea_el_trabajo_ni_se_copia(
    client: TestClient, db: Session
) -> None:
    from app.models import Trabajo

    cola = ColaDoble(caida=True)
    app.dependency_overrides[obtener_cola] = lambda: cola

    respuesta = _subir_lote(client)

    assert respuesta.status_code == 503
    assert cola.verificaciones == 1  # se preguntó ANTES de crear nada
    assert db.query(Trabajo).count() == 0
    assert not settings.INGESTA_TEMPORAL.exists()


def test_si_falla_la_copia_se_descarta_el_trabajo_y_su_carpeta(
    client: TestClient, cola: ColaDoble, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models import Trabajo

    def copia_rota(*_argumentos: object) -> list[Path]:
        (settings.INGESTA_TEMPORAL / "a-medias").mkdir(parents=True)
        raise OSError("disco lleno")

    monkeypatch.setattr("app.routers.trabajos._guardar_copias", copia_rota)

    with pytest.raises(OSError, match="disco lleno"):
        _subir_lote(client)

    assert db.query(Trabajo).count() == 0
    assert cola.encolados == []


# ── C12: el router no arrastra al worker ────────────────────────────────────


def test_el_router_no_importa_el_worker() -> None:
    import subprocess
    import sys

    codigo = "import sys, app.routers.trabajos; print('app.worker' in sys.modules)"
    salida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, check=True
    )

    assert salida.stdout.strip() == "False"


def test_las_funciones_de_arq_se_registran_con_nombre_explicito() -> None:
    from app.config.constantes import FUNCION_BARRER, FUNCION_INGESTAR, FUNCION_SINCRONIZAR
    from app.worker import WorkerSettings

    nombres = {funcion.name for funcion in WorkerSettings.functions}

    assert nombres == {FUNCION_INGESTAR, FUNCION_SINCRONIZAR}
    assert [tarea.name for tarea in WorkerSettings.cron_jobs] == [FUNCION_BARRER]
