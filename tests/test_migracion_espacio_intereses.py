"""La migración que renombra el espacio «laboral» a «intereses»: idempotente y sin pisar nada."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Espacio
from app.services import catalogo

CARPETA_MIGRACIONES = Path(__file__).parent.parent / "alembic" / "versions"
SLUG_ANTERIOR = "laboral"
SLUG_NUEVO = "intereses"


def _cargar_migracion() -> ModuleType:
    # Una migración no es un paquete importable: se carga por su ruta.
    ruta = next(CARPETA_MIGRACIONES.glob("*_espacio_laboral_pasa_a_intereses.py"))
    spec = importlib.util.spec_from_file_location("migracion_espacio_intereses", ruta)
    assert spec is not None and spec.loader is not None, f"no se pudo cargar {ruta.name}"
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _renombrar(db: Session, origen: str, destino: str, nombre_destino: str) -> None:
    migracion = _cargar_migracion()
    db.execute(
        migracion.RENOMBRAR_ESPACIO,
        {"origen": origen, "destino": destino, "nombre_destino": nombre_destino},
    )
    db.expire_all()


def _slugs(db: Session) -> list[str]:
    return list(db.scalars(select(Espacio.slug).order_by(Espacio.slug)))


def test_renombra_laboral_a_intereses_y_conserva_el_id(db: Session) -> None:
    original = catalogo.crear_espacio(db, SLUG_ANTERIOR, "Laboral")
    id_original = original.id

    _renombrar(db, SLUG_ANTERIOR, SLUG_NUEVO, "Intereses")

    renombrado = db.get(Espacio, id_original)
    assert renombrado is not None
    assert (renombrado.slug, renombrado.nombre) == (SLUG_NUEVO, "Intereses")


def test_es_idempotente_si_ya_se_llama_intereses(db: Session) -> None:
    catalogo.crear_espacio(db, SLUG_NUEVO, "Intereses")

    _renombrar(db, SLUG_ANTERIOR, SLUG_NUEVO, "Intereses")

    assert _slugs(db) == [SLUG_NUEVO]


def test_no_hace_nada_en_una_base_sin_laboral(db: Session) -> None:
    antes = _slugs(db)

    _renombrar(db, SLUG_ANTERIOR, SLUG_NUEVO, "Intereses")

    assert _slugs(db) == antes


def test_no_pisa_un_intereses_que_ya_existe(db: Session) -> None:
    catalogo.crear_espacio(db, SLUG_ANTERIOR, "Laboral")
    catalogo.crear_espacio(db, SLUG_NUEVO, "Intereses")

    _renombrar(db, SLUG_ANTERIOR, SLUG_NUEVO, "Intereses")

    assert _slugs(db) == [SLUG_NUEVO, SLUG_ANTERIOR]  # orden alfabético: intereses < laboral


def test_la_vuelta_deja_laboral_donde_estaba_intereses(db: Session) -> None:
    catalogo.crear_espacio(db, SLUG_NUEVO, "Intereses")

    _renombrar(db, SLUG_NUEVO, SLUG_ANTERIOR, "Laboral")

    assert _slugs(db) == [SLUG_ANTERIOR]
