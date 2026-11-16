"""Sincroniza una colección con un conector: la copia indexada refleja la fuente.

Por registro (cada uno en su transacción): nuevo → se ingiere; mismo hash → sin cambios; hash
distinto → el documento anterior se reemplaza en el mismo commit; ausente en la fuente → se borra.
Si la fuente no responde no se toca nada: una fuente caída no vacía la colección.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.conectores.base import Conector, ErrorConector, Registro
from app.models import Documento
from app.providers.embeddings import ProveedorDeEmbeddings
from app.services import catalogo
from app.services.deteccion import hash_contenido
from app.services.ingesta_por_lotes import Resultado, ResultadoArchivo, ingestar_en_lote


class Cambio(StrEnum):
    NUEVO = "nuevo"
    ACTUALIZADO = "actualizado"
    SIN_CAMBIOS = "sin_cambios"
    DUPLICADO = "duplicado"  # texto idéntico al de otro registro: no se indexa dos veces
    RECHAZADO = "rechazado"
    ERROR = "error"


@dataclass(frozen=True)
class ResumenSincronizacion:
    nuevos: int
    actualizados: int
    sin_cambios: int
    duplicados: int
    eliminados: int
    rechazados: int
    errores: int

    @property
    def procesados(self) -> int:
        """Registros de la fuente (las bajas no lo son: se cuentan aparte)."""
        return (
            self.nuevos
            + self.actualizados
            + self.sin_cambios
            + self.duplicados
            + self.rechazados
            + self.errores
        )


@dataclass(frozen=True)
class _Existente:
    documento_id: int
    hash_contenido: str


def sincronizar_coleccion(
    db: Session,
    espacio: str,
    coleccion: str,
    conector: Conector,
    proveedor: ProveedorDeEmbeddings,
    contar: Callable[[Session, ResultadoArchivo], None] | None = None,
    *,
    permitir_vaciar: bool = False,
) -> ResumenSincronizacion:
    """`contar(db, archivo)`: avance de un trabajo en segundo plano, en la misma transacción que
    cada registro (ver `ingestar_en_lote`). El total y las bajas los fija quien llama, al final.

    `permitir_vaciar`: una fuente que responde sin registros borra la colección SOLO si se pide;
    si no, es un error (una respuesta vacía por una falla de la fuente no debe vaciarla).
    """
    registros = conector.registros()  # si la fuente falla, se propaga antes de tocar nada
    _rechazar_ids_repetidos(registros)
    existentes = _existentes(db, espacio, coleccion)
    db.commit()
    if not registros and existentes and not permitir_vaciar:
        raise ErrorConector(
            f"La fuente devolvió 0 registros y la colección tiene {len(existentes)}: no se borra "
            "nada. Para vaciarla, pedirlo explícitamente (permitir_vaciar)."
        )

    totales: Counter[Cambio] = Counter()
    for registro in registros:
        anterior = existentes.get(registro.id_externo)
        cambio, _archivo = _sincronizar_registro(
            db, espacio, coleccion, registro, anterior, proveedor, contar
        )
        totales[cambio] += 1

    ausentes = set(existentes) - {registro.id_externo for registro in registros}
    eliminados = _borrar(db, [existentes[id_externo].documento_id for id_externo in ausentes])
    return ResumenSincronizacion(
        nuevos=totales[Cambio.NUEVO],
        actualizados=totales[Cambio.ACTUALIZADO],
        sin_cambios=totales[Cambio.SIN_CAMBIOS],
        duplicados=totales[Cambio.DUPLICADO],
        eliminados=eliminados,
        rechazados=totales[Cambio.RECHAZADO],
        errores=totales[Cambio.ERROR],
    )


def _rechazar_ids_repetidos(registros: list[Registro]) -> None:
    """Con ids repetidos, el segundo registro se confundiría con el primero y no se indexaría."""
    ids = [registro.id_externo for registro in registros]
    repetidos = sorted({id_externo for id_externo in ids if ids.count(id_externo) > 1})
    if repetidos:
        raise ErrorConector(f"La fuente repite ids de registro: {repetidos}")


def _existentes(db: Session, espacio: str, coleccion: str) -> dict[str, _Existente]:
    destino = catalogo.obtener_coleccion(db, espacio, coleccion)
    consulta = select(Documento.id_externo, Documento.id, Documento.hash_contenido).where(
        Documento.coleccion_id == destino.id, Documento.id_externo.is_not(None)
    )
    return {
        id_externo: _Existente(documento_id, hash_)
        for id_externo, documento_id, hash_ in db.execute(consulta)
        if id_externo is not None
    }


def _sincronizar_registro(
    db: Session,
    espacio: str,
    coleccion: str,
    registro: Registro,
    anterior: _Existente | None,
    proveedor: ProveedorDeEmbeddings,
    contar: Callable[[Session, ResultadoArchivo], None] | None,
) -> tuple[Cambio, ResultadoArchivo]:
    contenido = registro.texto.encode()
    if anterior is not None and anterior.hash_contenido == hash_contenido(contenido):
        sin_cambios = ResultadoArchivo(Resultado.SIN_CAMBIOS, 0, None)
        if contar is not None:
            contar(db, sin_cambios)
            db.commit()
        return Cambio.SIN_CAMBIOS, sin_cambios
    archivo = ingestar_en_lote(
        db,
        espacio,
        coleccion,
        registro.titulo,
        contenido,
        proveedor,
        None,  # los registros son texto: no hay páginas para la visión
        f"[{registro.id_externo}]",
        id_externo=registro.id_externo,
        reemplaza_a=anterior.documento_id if anterior else None,
        contar=contar,
    )
    return _cambio(archivo, hay_anterior=anterior is not None), archivo


def _cambio(archivo: ResultadoArchivo, hay_anterior: bool) -> Cambio:
    if archivo.resultado == Resultado.INGERIDO:
        return Cambio.ACTUALIZADO if hay_anterior else Cambio.NUEVO
    if archivo.resultado == Resultado.DUPLICADO:
        return Cambio.DUPLICADO
    if archivo.resultado == Resultado.ERROR:
        return Cambio.ERROR
    return Cambio.RECHAZADO


def _borrar(db: Session, documento_ids: list[int]) -> int:
    if not documento_ids:
        return 0
    db.execute(delete(Documento).where(Documento.id.in_(documento_ids)))
    db.commit()
    return len(documento_ids)
