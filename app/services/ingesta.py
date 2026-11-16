"""Ingesta de un archivo: detectar → extraer → embeber → guardar documento y trozos juntos."""

import unicodedata
from dataclasses import dataclass
from http import HTTPStatus

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.errors import AppError, unprocessable
from app.config.constantes import MAX_LARGO_NOMBRE_ARCHIVO, NOMBRE_ARCHIVO_POR_DEFECTO
from app.models import Coleccion, Documento, Trozo
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_documentos
from app.services.deteccion import detectar
from app.services.extraccion import extraer

CATEGORIA_CONTROL = "Cc"  # Unicode: NUL, saltos de línea, tabuladores...


class DocumentoDuplicado(AppError):
    """El mismo contenido ya está en la colección. Tipo propio: quien llama no compara códigos."""

    def __init__(self, message: str) -> None:
        super().__init__(HTTPStatus.CONFLICT, message)


@dataclass(frozen=True)
class ResultadoIngesta:
    documento: Documento
    trozos: int
    paginas_sin_texto: list[int]


def ingestar(
    db: Session,
    coleccion: Coleccion,
    nombre_archivo: str,
    contenido: bytes,
    proveedor: ProveedorDeEmbeddings,
) -> ResultadoIngesta:
    nombre = _nombre_valido(nombre_archivo)
    detectado = detectar(contenido)
    _rechazar_si_ya_existe(db, coleccion, detectado.hash_contenido)
    coleccion_id = coleccion.id
    # Las lecturas de arriba (y la de la colección, hecha por quien llama) abrieron una
    # transacción. Se cierra aquí: extraer y embeber tardan minutos y la conexión no debe
    # quedar «idle in transaction» mientras tanto. La escritura abre una nueva en `_guardar`.
    db.commit()

    extraccion = extraer(contenido, detectado.tipo, nombre)
    if not extraccion.trozos:
        raise unprocessable(
            "El archivo no tiene texto extraíble (¿escaneado?). "
            "Las páginas sin texto se indexarán con visión en la FASE_2."
        )
    vectores = embeber_documentos(proveedor, [trozo.texto for trozo in extraccion.trozos])

    documento = Documento(
        coleccion_id=coleccion_id,
        nombre_archivo=nombre,
        hash_contenido=detectado.hash_contenido,
        tipo=detectado.tipo,
        paginas=extraccion.paginas,
        trozos=[
            Trozo(
                orden=orden,
                texto=trozo.texto,
                pagina_inicio=trozo.pagina_inicio,
                pagina_fin=trozo.pagina_fin,
                embedding=vector,
                embedding_model=proveedor.modelo_id,
            )
            for orden, (trozo, vector) in enumerate(zip(extraccion.trozos, vectores, strict=True))
        ],
    )
    _guardar(db, documento, coleccion)
    return ResultadoIngesta(
        documento=documento,
        trozos=len(extraccion.trozos),
        paginas_sin_texto=extraccion.paginas_sin_texto,
    )


def _nombre_valido(nombre: str) -> str:
    """El nombre es lo que se muestra en la cita: sin control (Postgres rechaza NUL) y acotado."""
    limpio = nombre.strip()
    if not limpio:
        return NOMBRE_ARCHIVO_POR_DEFECTO
    if len(limpio) > MAX_LARGO_NOMBRE_ARCHIVO:
        raise unprocessable(
            f"El nombre del archivo supera los {MAX_LARGO_NOMBRE_ARCHIVO} caracteres"
        )
    if any(unicodedata.category(caracter) == CATEGORIA_CONTROL for caracter in limpio):
        raise unprocessable("El nombre del archivo tiene caracteres de control")
    return limpio


def _rechazar_si_ya_existe(db: Session, coleccion: Coleccion, hash_contenido: str) -> None:
    """Chequeo temprano para no extraer ni embeber en vano; la restricción única es la garantía."""
    existente = db.scalar(
        select(Documento).where(
            Documento.coleccion_id == coleccion.id, Documento.hash_contenido == hash_contenido
        )
    )
    if existente is not None:
        raise _duplicado(coleccion, existente.nombre_archivo)


def _guardar(db: Session, documento: Documento, coleccion: Coleccion) -> None:
    """Documento y trozos en UN commit: o entra todo o no entra nada."""
    db.add(documento)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()  # otra subida del mismo archivo ganó la carrera
        raise _duplicado(coleccion, documento.nombre_archivo) from error
    db.refresh(documento)


def _duplicado(coleccion: Coleccion, nombre_existente: str) -> DocumentoDuplicado:
    return DocumentoDuplicado(
        f"Ese contenido ya está en la colección «{coleccion.slug}» como «{nombre_existente}»"
    )
