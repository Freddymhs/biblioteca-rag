"""Ingesta de un archivo: detectar → extraer → embeber → guardar documento y trozos juntos."""

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus

from langchain_core.language_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.errors import AppError, unprocessable
from app.config.constantes import MAX_LARGO_NOMBRE_ARCHIVO, NOMBRE_ARCHIVO_POR_DEFECTO
from app.models import Coleccion, Documento, Trozo
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_documentos
from app.services.deteccion import detectar
from app.services.extraccion import extraer
from app.services.vision import indexar_paginas_sin_texto

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
    paginas_por_vision: list[int]
    paginas_en_blanco: list[int]
    paginas_sin_indexar: list[int]


def ingestar(
    db: Session,
    coleccion: Coleccion,
    nombre_archivo: str,
    contenido: bytes,
    proveedor: ProveedorDeEmbeddings,
    *,
    vision: BaseChatModel | None,
    id_externo: str | None = None,
    reemplaza_a: int | None = None,
    al_guardar: Callable[[Session, int], None] | None = None,
) -> ResultadoIngesta:
    """`reemplaza_a`: id de un documento que este sustituye en el MISMO commit (conectores).
    `al_guardar(db, trozos)`: corre dentro de la transacción del documento, antes del commit
    (el contador de un trabajo: o quedan los dos o ninguno)."""
    nombre = _nombre_valido(nombre_archivo)
    detectado = detectar(contenido)
    _rechazar_si_ya_existe(db, coleccion, detectado.hash_contenido)
    coleccion_id = coleccion.id
    # Las lecturas de arriba (y la de la colección, hecha por quien llama) abrieron una
    # transacción. Se cierra aquí: extraer y embeber tardan minutos y la conexión no debe
    # quedar «idle in transaction» mientras tanto. La escritura abre una nueva en `_guardar`.
    db.commit()

    extraccion = extraer(contenido, detectado.tipo, nombre)
    por_vision = indexar_paginas_sin_texto(contenido, extraccion.paginas_sin_texto, vision, nombre)
    trozos = extraccion.trozos + por_vision.trozos
    if not trozos:
        raise unprocessable(
            "El archivo no tiene texto extraíble ni páginas que el modelo de visión pudiera "
            "describir (¿escaneado en blanco, o visión desactivada?)"
        )
    vectores = embeber_documentos(proveedor, [trozo.texto for trozo in trozos])

    documento = Documento(
        coleccion_id=coleccion_id,
        nombre_archivo=nombre,
        id_externo=id_externo,
        hash_contenido=detectado.hash_contenido,
        tipo=detectado.tipo,
        paginas=extraccion.paginas,
        estructura=extraccion.estructura,
        trozos=[
            Trozo(
                orden=orden,
                texto=trozo.texto,
                pagina_inicio=trozo.pagina_inicio,
                pagina_fin=trozo.pagina_fin,
                origen=trozo.origen,
                embedding=vector,
                embedding_model=proveedor.modelo_id,
            )
            for orden, (trozo, vector) in enumerate(zip(trozos, vectores, strict=True))
        ],
    )
    _guardar(db, documento, coleccion, reemplaza_a, al_guardar, len(trozos))
    return ResultadoIngesta(
        documento=documento,
        trozos=len(trozos),
        paginas_sin_texto=extraccion.paginas_sin_texto,
        paginas_por_vision=por_vision.descritas,
        paginas_en_blanco=por_vision.en_blanco,
        paginas_sin_indexar=por_vision.sin_indexar,
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


def _guardar(
    db: Session,
    documento: Documento,
    coleccion: Coleccion,
    reemplaza_a: int | None,
    al_guardar: Callable[[Session, int], None] | None,
    trozos: int,
) -> None:
    """Documento y trozos en UN commit: o entra todo o no entra nada."""
    if reemplaza_a is not None:
        db.delete(db.get_one(Documento, reemplaza_a))
        db.flush()  # libera su id externo antes de insertar el nuevo, dentro de la transacción
    try:
        db.add(documento)
        # `add` solo no abre transacción: sin este flush, un rollback no descarta el documento
        # pendiente y el próximo autoflush de la sesión (ej. contar el error) lo insertaría.
        db.flush()
        if al_guardar is not None:
            al_guardar(db, trozos)
        db.commit()
    except IntegrityError as error:
        db.rollback()  # otra subida del mismo archivo ganó la carrera
        raise _duplicado(coleccion, documento.nombre_archivo) from error
    except Exception:
        db.rollback()
        raise
    db.refresh(documento)


def _duplicado(coleccion: Coleccion, nombre_existente: str) -> DocumentoDuplicado:
    return DocumentoDuplicado(
        f"Ese contenido ya está en la colección «{coleccion.slug}» como «{nombre_existente}»"
    )
