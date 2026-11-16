"""Re-embed de una colección desde el texto guardado: al cambiar de modelo o de troceo.

Cada documento se reemplaza en UNA transacción: una búsqueda nunca ve un documento a medias, y
mientras dura el proceso cada búsqueda solo ve los documentos del modelo activo (no mezcla).
"""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import unprocessable
from app.common.logger import logger
from app.config.constantes import OrigenTrozo
from app.models import Documento, Trozo
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_documentos
from app.services import catalogo
from app.services.extraccion import TrozoExtraido, trocear_estructura

ORIGENES_CONSERVADOS = {OrigenTrozo.VISION, OrigenTrozo.DATOS}


class Resultado(StrEnum):
    REEMBEBIDO = "documentos"
    SALTADO = "saltados"  # ya estaba con el modelo activo
    SIN_ESTRUCTURA = "sin_estructura"  # se pidió re-trocear y no hay DoclingDocument guardado


@dataclass(frozen=True)
class ResumenReembebido:
    documentos: int
    trozos: int
    saltados: int
    sin_estructura: int


@dataclass(frozen=True)
class _Lectura:
    trozos: list[TrozoExtraido]
    modelos: set[str]
    estructura: dict[str, Any] | None


def reembeber_coleccion(
    db: Session,
    espacio: str,
    coleccion: str,
    proveedor: ProveedorDeEmbeddings,
    *,
    retrocear: bool = False,
) -> ResumenReembebido:
    destino = catalogo.obtener_coleccion(db, espacio, coleccion)
    if retrocear and destino.paquete is not None:
        # Re-trocear embebería el texto crudo de Docling, también el de extracciones pendientes:
        # lo buscable de estas colecciones es solo lo confirmado (su trozo de datos).
        raise unprocessable(
            f"La colección «{destino.slug}» usa el paquete «{destino.paquete}»: no se re-trocea; "
            "re-embeber sin --retrocear conserva sus datos confirmados"
        )
    consulta = select(Documento.id).where(Documento.coleccion_id == destino.id)
    ids = list(db.scalars(consulta.order_by(Documento.id)))
    db.commit()

    totales: Counter[str] = Counter()
    for documento_id in ids:
        resultado, trozos = _reembeber_documento(db, documento_id, proveedor, retrocear)
        totales[resultado] += 1
        totales["trozos"] += trozos
    return ResumenReembebido(
        documentos=totales[Resultado.REEMBEBIDO],
        trozos=totales["trozos"],
        saltados=totales[Resultado.SALTADO],
        sin_estructura=totales[Resultado.SIN_ESTRUCTURA],
    )


def _reembeber_documento(
    db: Session, documento_id: int, proveedor: ProveedorDeEmbeddings, retrocear: bool
) -> tuple[Resultado, int]:
    lectura = _leer(db, documento_id)
    db.commit()  # embeber tarda: la conexión no queda «idle in transaction» (ver ingesta)

    if not retrocear and lectura.modelos == {proveedor.modelo_id}:
        return Resultado.SALTADO, 0
    if retrocear and lectura.estructura is None:
        logger.warning(f"documento {documento_id}: sin estructura guardada, no se re-trocea")
        return Resultado.SIN_ESTRUCTURA, 0

    nuevos = _trozos_nuevos(lectura, retrocear)
    vectores = embeber_documentos(proveedor, [trozo.texto for trozo in nuevos])

    documento = db.get_one(Documento, documento_id)
    documento.trozos = [  # delete-orphan borra los anteriores en el mismo commit
        Trozo(
            orden=orden,
            texto=trozo.texto,
            pagina_inicio=trozo.pagina_inicio,
            pagina_fin=trozo.pagina_fin,
            origen=trozo.origen,
            embedding=vector,
            embedding_model=proveedor.modelo_id,
        )
        for orden, (trozo, vector) in enumerate(zip(nuevos, vectores, strict=True))
    ]
    db.commit()
    return Resultado.REEMBEBIDO, len(nuevos)


def _leer(db: Session, documento_id: int) -> _Lectura:
    documento = db.get_one(Documento, documento_id)
    trozos = sorted(documento.trozos, key=lambda trozo: trozo.orden)
    return _Lectura(
        trozos=[TrozoExtraido(t.texto, t.pagina_inicio, t.pagina_fin, t.origen) for t in trozos],
        modelos={trozo.embedding_model for trozo in trozos},
        estructura=documento.estructura,
    )


def _trozos_nuevos(lectura: _Lectura, retrocear: bool) -> list[TrozoExtraido]:
    if not retrocear or lectura.estructura is None:
        return lectura.trozos
    # Lo que no sale de Docling (visión, datos confirmados) se conserva tal cual.
    conservados = [trozo for trozo in lectura.trozos if trozo.origen in ORIGENES_CONSERVADOS]
    return trocear_estructura(lectura.estructura) + conservados
