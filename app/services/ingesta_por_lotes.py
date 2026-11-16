"""Ingesta de un archivo dentro de un lote (carpeta por CLI o trabajo en segundo plano).

A diferencia del endpoint de un archivo, aquí ningún fallo se propaga: se clasifica y se sigue
con el siguiente. Lo usan `app/cli/ingestar.py` y `app/worker.py`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorProveedor
from app.common.logger import logger
from app.providers.embeddings import ProveedorDeEmbeddings
from app.services import catalogo
from app.services.ingesta import DocumentoDuplicado, ingestar


class Resultado(StrEnum):
    INGERIDO = "ingeridos"
    DUPLICADO = "duplicados"  # mismo contenido que otro documento de la colección
    SIN_CAMBIOS = "sin_cambios"  # sincronización: el registro no cambió en la fuente
    RECHAZADO = "rechazados"
    ERROR = "errores"


@dataclass(frozen=True)
class ResultadoArchivo:
    resultado: Resultado
    trozos: int
    mensaje: str | None  # el motivo cuando no se ingirió


def ingestar_en_lote(
    db: Session,
    espacio: str,
    coleccion: str,
    nombre: str,
    contenido: bytes,
    proveedor: ProveedorDeEmbeddings,
    vision: BaseChatModel | None,
    prefijo: str,
    *,
    id_externo: str | None = None,
    reemplaza_a: int | None = None,
    contar: Callable[[Session, ResultadoArchivo], None] | None = None,
) -> ResultadoArchivo:
    """`contar(db, archivo)` no confirma: si el archivo entra, va en la transacción del documento;
    si no, en una propia. Así ningún resultado queda sin contar ni contado dos veces."""
    archivo = _ingestar_clasificado(
        db, espacio, coleccion, nombre, contenido, proveedor, vision, prefijo,
        id_externo, reemplaza_a, contar,
    )  # fmt: skip
    if contar is not None and archivo.resultado != Resultado.INGERIDO:
        contar(db, archivo)
        db.commit()
    return archivo


def _ingestar_clasificado(
    db: Session,
    espacio: str,
    coleccion: str,
    nombre: str,
    contenido: bytes,
    proveedor: ProveedorDeEmbeddings,
    vision: BaseChatModel | None,
    prefijo: str,
    id_externo: str | None,
    reemplaza_a: int | None,
    contar: Callable[[Session, ResultadoArchivo], None] | None,
) -> ResultadoArchivo:
    al_guardar = None
    if contar is not None:
        al_guardar = lambda db_, trozos: contar(  # noqa: E731 — cierra sobre `contar`
            db_, ResultadoArchivo(Resultado.INGERIDO, trozos, None)
        )
    try:
        destino = catalogo.obtener_coleccion(db, espacio, coleccion)
        resultado = ingestar(
            db,
            destino,
            nombre,
            contenido,
            proveedor,
            vision=vision,
            id_externo=id_externo,
            reemplaza_a=reemplaza_a,
            al_guardar=al_guardar,
        )
    except DocumentoDuplicado as error:
        return _registrar(prefijo, Resultado.DUPLICADO, error.message)
    except AppError as error:
        return _registrar(prefijo, Resultado.RECHAZADO, error.message)
    except ErrorProveedor as error:
        return _registrar(prefijo, Resultado.ERROR, f"proveedor — {error}")
    except Exception as error:
        # Inesperado: se registra con traza y se sigue con el siguiente archivo.
        logger.exception(f"{prefijo}: error inesperado")
        db.rollback()
        return ResultadoArchivo(Resultado.ERROR, 0, f"error inesperado: {error!r}")
    logger.info(f"{prefijo}: {resultado.trozos} trozos")
    return ResultadoArchivo(Resultado.INGERIDO, resultado.trozos, None)


def _registrar(prefijo: str, resultado: Resultado, mensaje: str) -> ResultadoArchivo:
    nivel = logger.error if resultado == Resultado.ERROR else logger.warning
    nivel(f"{prefijo}: {resultado.value} — {mensaje}")
    return ResultadoArchivo(resultado, 0, mensaje)
