"""Alta y consulta de espacios y colecciones: el dominio vive en la base, no en el código."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.errors import conflict, not_found
from app.models import Coleccion, Espacio


def crear_espacio(db: Session, slug: str, nombre: str) -> Espacio:
    espacio = Espacio(slug=slug, nombre=nombre)
    _guardar(db, espacio, f"Ya existe el espacio «{slug}»")
    return espacio


def listar_espacios(db: Session) -> list[Espacio]:
    return list(db.scalars(select(Espacio).order_by(Espacio.slug)))


def obtener_espacio(db: Session, slug: str) -> Espacio:
    espacio = db.scalar(select(Espacio).where(Espacio.slug == slug))
    if espacio is None:
        raise not_found(f"El espacio «{slug}»")
    return espacio


def crear_coleccion(db: Session, espacio_slug: str, slug: str, nombre: str) -> Coleccion:
    espacio = obtener_espacio(db, espacio_slug)
    coleccion = Coleccion(espacio=espacio, slug=slug, nombre=nombre)
    _guardar(db, coleccion, f"Ya existe la colección «{slug}» en «{espacio_slug}»")
    return coleccion


def listar_colecciones(db: Session, espacio_slug: str) -> list[Coleccion]:
    espacio = obtener_espacio(db, espacio_slug)
    consulta = select(Coleccion).where(Coleccion.espacio_id == espacio.id).order_by(Coleccion.slug)
    return list(db.scalars(consulta))


def obtener_coleccion(db: Session, espacio_slug: str, slug: str) -> Coleccion:
    consulta = (
        select(Coleccion).join(Espacio).where(Espacio.slug == espacio_slug, Coleccion.slug == slug)
    )
    coleccion = db.scalar(consulta)
    if coleccion is None:
        obtener_espacio(db, espacio_slug)  # distingue «no existe el espacio» de «la colección»
        raise not_found(f"La colección «{slug}» en «{espacio_slug}»")
    return coleccion


def _guardar(db: Session, entidad: Espacio | Coleccion, mensaje_duplicado: str) -> None:
    """La restricción única de la base decide el duplicado: sin carrera entre leer y escribir."""
    db.add(entidad)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise conflict(mensaje_duplicado) from error
    db.refresh(entidad)
