from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models import Coleccion, Espacio
from app.schemas.catalogo import (
    ColeccionCrear,
    ColeccionPublicar,
    ColeccionRespuesta,
    EspacioCrear,
    EspacioRespuesta,
)
from app.services import catalogo

router = APIRouter(prefix="/espacios", tags=["espacios y colecciones"])


@router.post("", response_model=EspacioRespuesta, status_code=status.HTTP_201_CREATED)
def crear_espacio(datos: EspacioCrear, db: Session = Depends(get_db)) -> Espacio:
    return catalogo.crear_espacio(db, datos.slug, datos.nombre)


@router.get("", response_model=list[EspacioRespuesta])
def listar_espacios(db: Session = Depends(get_db)) -> list[Espacio]:
    return catalogo.listar_espacios(db)


@router.post(
    "/{espacio}/colecciones",
    response_model=ColeccionRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def crear_coleccion(
    espacio: str, datos: ColeccionCrear, db: Session = Depends(get_db)
) -> ColeccionRespuesta:
    return _respuesta_coleccion(
        catalogo.crear_coleccion(db, espacio, datos.slug, datos.nombre, datos.paquete)
    )


@router.get("/{espacio}/colecciones", response_model=list[ColeccionRespuesta])
def listar_colecciones(espacio: str, db: Session = Depends(get_db)) -> list[ColeccionRespuesta]:
    return [_respuesta_coleccion(c) for c in catalogo.listar_colecciones(db, espacio)]


@router.patch("/{espacio}/colecciones/{coleccion}", response_model=ColeccionRespuesta)
def publicar_coleccion(
    espacio: str, coleccion: str, datos: ColeccionPublicar, db: Session = Depends(get_db)
) -> ColeccionRespuesta:
    return _respuesta_coleccion(catalogo.publicar_coleccion(db, espacio, coleccion, datos.publica))


def _respuesta_coleccion(coleccion: Coleccion) -> ColeccionRespuesta:
    return ColeccionRespuesta(
        id=coleccion.id,
        espacio=coleccion.espacio.slug,
        slug=coleccion.slug,
        nombre=coleccion.nombre,
        paquete=coleccion.paquete,
        publica=coleccion.publica,
        creado_en=coleccion.creado_en,
    )
