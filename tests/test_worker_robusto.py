"""Auditoría FASE_2, puntos C3, C4, C7, C8 y C9: que ningún archivo quede sin contar ni ningún
trabajo «en curso» para siempre. C3 usa Redis real: el estado de las tareas lo decide arq."""

import asyncio
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.conectores.base import Registro
from app.config.constantes import MAX_BYTES_SUBIDA, TipoTrabajo
from app.config.settings import settings
from app.models import Documento, Trabajo
from app.services import catalogo
from app.services.ingesta_por_lotes import ResultadoArchivo
from app.services.trabajos import crear_trabajo, id_tarea_archivo, obtener_trabajo
from app.worker import (
    MOTIVO_HUERFANO,
    barrer_trabajos_huerfanos,
    procesar_archivo,
    procesar_sincronizacion,
)
from tests.dobles import proveedor_doble
from tests.pdf_minimo import pdf_minimo

PDF = pdf_minimo(["Riego del olivo"])


@pytest.fixture(autouse=True)
def coleccion(db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "INGESTA_TEMPORAL", tmp_path / "ingesta")
    catalogo.crear_espacio(db, "laboral", "Laboral")
    catalogo.crear_coleccion(db, "laboral", "agricultura", "Agricultura")


@pytest.fixture
def sesion(db: Session):
    @contextmanager
    def _sesion() -> Generator[Session, None, None]:
        yield db

    return _sesion


def _trabajo(db: Session, total: int | None, tipo: TipoTrabajo = TipoTrabajo.LOTE) -> Trabajo:
    destino = catalogo.obtener_coleccion(db, "laboral", "agricultura")
    return crear_trabajo(db, destino, tipo, total)


def _copia(trabajo_id: int, indice: int, contenido: bytes) -> Path:
    carpeta = settings.INGESTA_TEMPORAL / str(trabajo_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{indice:05d}"
    ruta.write_bytes(contenido)
    return ruta


def _procesar(
    sesion: Callable[[], AbstractContextManager[Session]],
    trabajo_id: int,
    ruta: Path,
    nombre: str = "olivo.pdf",
) -> ResultadoArchivo:
    return procesar_archivo(sesion, proveedor_doble, lambda: None, trabajo_id, ruta, nombre)


def _documentos(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Documento)) or 0


# ── C4: toda excepción cuenta como error ──────────────────────────────────────


def test_copia_que_no_existe_cuenta_como_error_y_el_trabajo_termina(db: Session, sesion) -> None:
    trabajo = _trabajo(db, total=1)
    perdida = settings.INGESTA_TEMPORAL / str(trabajo.id) / "00000"

    archivo = _procesar(sesion, trabajo.id, perdida)

    db.refresh(trabajo)
    assert archivo.resultado.value == "errores"
    assert (trabajo.estado.value, trabajo.errores) == ("terminado", 1)
    assert "FileNotFoundError" in (trabajo.ultimo_error or "")


# ── C7: la ruta que llega por Redis se valida antes de leerla o borrarla ─────


def test_ruta_fuera_de_la_carpeta_temporal_no_se_lee_ni_se_borra(
    db: Session, sesion, tmp_path: Path
) -> None:
    trabajo = _trabajo(db, total=1)
    ajena = tmp_path / "no-es-del-lote.pdf"
    ajena.write_bytes(PDF)

    archivo = _procesar(sesion, trabajo.id, ajena)

    assert archivo.resultado.value == "errores"
    assert ajena.exists()
    assert _documentos(db) == 0


def test_copia_demasiado_grande_se_rechaza_sin_leerla(
    db: Session, sesion, monkeypatch: pytest.MonkeyPatch
) -> None:
    trabajo = _trabajo(db, total=1)
    ruta = _copia(trabajo.id, 0, PDF)
    monkeypatch.setattr("app.worker.MAX_BYTES_SUBIDA", len(PDF) - 1)

    archivo = _procesar(sesion, trabajo.id, ruta)

    assert archivo.resultado.value == "rechazados"
    assert not ruta.exists()  # es nuestra: se borra
    assert len(PDF) < MAX_BYTES_SUBIDA


# ── C9: documento y contador en la misma transacción ─────────────────────────


def test_si_falla_el_contador_tampoco_queda_el_documento(
    db: Session, sesion, monkeypatch: pytest.MonkeyPatch
) -> None:
    trabajo = _trabajo(db, total=1)
    ruta = _copia(trabajo.id, 0, PDF)

    def contador_roto(*_argumentos: object) -> None:
        raise RuntimeError("se cortó la base al contar")

    monkeypatch.setattr("app.worker.sumar_resultado", contador_roto)

    _procesar(sesion, trabajo.id, ruta)

    assert _documentos(db) == 0  # sin contador no hay documento: van juntos


# ── C8: «terminado» recién al final de la sincronización ─────────────────────


class ConectorDoble:
    nombre = "doble"

    def __init__(self, registros: list[Registro]) -> None:
        self.actuales = registros

    def registros(self) -> list[Registro]:
        return self.actuales


def test_la_sincronizacion_no_se_ve_terminada_antes_de_borrar_las_bajas(
    db: Session, sesion, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import worker

    viejo = Registro("work:viejo", "resume: viejo", "Sección: work\nsummary: Poda")
    nuevo = Registro("work:nuevo", "resume: nuevo", "Sección: work\nsummary: Riego")
    conector = ConectorDoble([viejo])
    primera = _trabajo(db, None, TipoTrabajo.SINCRONIZACION)
    procesar_sincronizacion(sesion, proveedor_doble, lambda _n: conector, primera.id, "d")
    conector.actuales = [nuevo]
    trabajo = _trabajo(db, None, TipoTrabajo.SINCRONIZACION)
    estados_durante: list[str] = []
    sumar_real = worker.sumar_resultado

    def sumar_espia(db_: Session, trabajo_id: int, archivo) -> None:
        sumar_real(db_, trabajo_id, archivo)
        db_.flush()
        estados_durante.append(obtener_trabajo(db_, trabajo_id).estado.value)

    monkeypatch.setattr(worker, "sumar_resultado", sumar_espia)

    procesar_sincronizacion(sesion, proveedor_doble, lambda _n: conector, trabajo.id, "d")

    db.refresh(trabajo)
    assert "terminado" not in estados_durante
    assert (trabajo.estado.value, trabajo.ingeridos, trabajo.eliminados) == ("terminado", 1, 1)


# ── C3: trabajos huérfanos (worker muerto o cola perdida), con Redis real ────


def test_el_barrido_cierra_solo_los_trabajos_sin_tareas_vivas_en_redis(
    db: Session, sesion, redis_url: str
) -> None:
    huerfano = _trabajo(db, total=2)
    _copia(huerfano.id, 0, PDF)
    con_tarea_en_cola = _trabajo(db, total=1)
    reciente = _trabajo(db, total=1)
    hace_una_hora = func.now() - timedelta(hours=1)
    db.execute(
        update(Trabajo)
        .where(Trabajo.id.in_([huerfano.id, con_tarea_en_cola.id]))
        .values(creado_en=hace_una_hora)
    )
    db.commit()

    async def barrer() -> int:
        pool = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            await pool.flushdb()
            # Una tarea encolada y sin worker que la tome: el trabajo NO está huérfano.
            await pool.enqueue_job(
                "ingestar_archivo", _job_id=id_tarea_archivo(con_tarea_en_cola.id, 0)
            )
            return await barrer_trabajos_huerfanos({"redis": pool, "abrir_sesion": sesion})
        finally:
            await pool.flushdb()  # Redis es compartido por la sesión de tests: no dejar tareas
            await pool.aclose()

    cerrados = asyncio.run(barrer())

    for trabajo in (huerfano, con_tarea_en_cola, reciente):
        db.refresh(trabajo)
    assert cerrados == 1
    assert (huerfano.estado.value, huerfano.errores, huerfano.ultimo_error) == (
        "terminado",
        2,
        MOTIVO_HUERFANO,
    )
    assert not (settings.INGESTA_TEMPORAL / str(huerfano.id)).exists()
    assert con_tarea_en_cola.estado.value == "pendiente"
    assert reciente.estado.value == "pendiente"
