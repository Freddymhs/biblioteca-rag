"""Trabajos de ingesta en segundo plano: alta, avance (contadores atómicos) y consulta."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.common.errors import not_found
from app.config.constantes import GRACIA_HUERFANOS_SEGUNDOS, TipoTrabajo
from app.models import Coleccion, Trabajo
from app.services.ingesta_por_lotes import Resultado, ResultadoArchivo

# Resultado de un archivo → columna del contador que suma.
COLUMNA_POR_RESULTADO = {
    Resultado.INGERIDO: Trabajo.ingeridos,
    Resultado.DUPLICADO: Trabajo.duplicados,
    Resultado.SIN_CAMBIOS: Trabajo.sin_cambios,
    Resultado.RECHAZADO: Trabajo.rechazados,
    Resultado.ERROR: Trabajo.errores,
}
# Un duplicado no es una falla: no pisa `ultimo_error`.
RESULTADOS_CON_FALLA = {Resultado.RECHAZADO, Resultado.ERROR}


def crear_trabajo(
    db: Session, coleccion: Coleccion, tipo: TipoTrabajo, total: int | None
) -> Trabajo:
    trabajo = Trabajo(coleccion_id=coleccion.id, tipo=tipo, total=total)
    db.add(trabajo)
    db.commit()
    db.refresh(trabajo)
    return trabajo


def obtener_trabajo(db: Session, trabajo_id: int) -> Trabajo:
    trabajo = db.get(Trabajo, trabajo_id)
    if trabajo is None:
        raise not_found(f"El trabajo {trabajo_id}")
    return trabajo


def id_tarea_archivo(trabajo_id: int, indice: int) -> str:
    """Id determinista de la tarea en arq: el barrido pregunta su estado a Redis por él."""
    return f"trabajo-{trabajo_id}-archivo-{indice}"


def id_tarea_sincronizacion(trabajo_id: int) -> str:
    return f"trabajo-{trabajo_id}-sincronizacion"


def ids_de_tareas(trabajo: Trabajo) -> list[str]:
    if trabajo.tipo == TipoTrabajo.SINCRONIZACION:
        return [id_tarea_sincronizacion(trabajo.id)]
    return [id_tarea_archivo(trabajo.id, indice) for indice in range(trabajo.total or 0)]


def sumar_resultado(db: Session, trabajo_id: int, archivo: ResultadoArchivo) -> None:
    """`columna = columna + 1` en SQL: dos workers no se pisan el conteo.

    No confirma: quien la llama la mete en la misma transacción que el documento (si lo hubo).
    """
    columna = COLUMNA_POR_RESULTADO[archivo.resultado]
    # `Any`: mezcla expresiones SQL (`columna + 1`) con valores literales (el mensaje).
    valores: dict[str, Any] = {
        columna.key: columna + 1,
        Trabajo.trozos.key: Trabajo.trozos + archivo.trozos,
    }
    if archivo.resultado in RESULTADOS_CON_FALLA and archivo.mensaje is not None:
        valores[Trabajo.ultimo_error.key] = archivo.mensaje
    db.execute(update(Trabajo).where(Trabajo.id == trabajo_id).values(valores))


def finalizar_sincronizacion(db: Session, trabajo_id: int, total: int, eliminados: int) -> None:
    """Total y bajas en un solo UPDATE: el trabajo pasa a «terminado» recién con todo contado."""
    valores = {
        Trabajo.total.key: total,
        Trabajo.eliminados.key: Trabajo.eliminados + eliminados,
    }
    db.execute(update(Trabajo).where(Trabajo.id == trabajo_id).values(valores))
    db.commit()


def cerrar_con_error(db: Session, trabajo_id: int, mensaje: str) -> None:
    """Falla de todo el trabajo (fuente caída, proveedor sin configurar): cuenta un error y fija
    el total en lo procesado, para que el trabajo termine con el motivo visible y no quede
    «pendiente» para siempre."""
    db.rollback()
    procesados_mas_uno = (
        Trabajo.ingeridos
        + Trabajo.duplicados
        + Trabajo.sin_cambios
        + Trabajo.rechazados
        + Trabajo.errores
        + 1
    )
    valores: dict[str, Any] = {
        Trabajo.errores.key: Trabajo.errores + 1,
        Trabajo.total.key: procesados_mas_uno,
        Trabajo.ultimo_error.key: mensaje,
    }
    db.execute(update(Trabajo).where(Trabajo.id == trabajo_id).values(valores))
    db.commit()


def trabajos_vencidos(db: Session) -> list[Trabajo]:
    """Sin terminar y creados hace más que la gracia: candidatos a huérfanos (el barrido confirma
    con Redis que no les queda ninguna tarea viva)."""
    limite = func.now() - timedelta(seconds=GRACIA_HUERFANOS_SEGUNDOS)
    procesados = (
        Trabajo.ingeridos
        + Trabajo.duplicados
        + Trabajo.sin_cambios
        + Trabajo.rechazados
        + Trabajo.errores
    )
    sin_terminar = or_(Trabajo.total.is_(None), procesados < Trabajo.total)
    consulta = select(Trabajo).where(Trabajo.creado_en < limite, sin_terminar)
    return list(db.scalars(consulta.order_by(Trabajo.id)))


def cerrar_huerfano(db: Session, trabajo_id: int, motivo: str) -> None:
    """Lo que faltaba procesar cuenta como error, con el motivo: el trabajo termina."""
    trabajo = obtener_trabajo(db, trabajo_id)
    pendientes = max((trabajo.total or trabajo.procesados + 1) - trabajo.procesados, 1)
    valores: dict[str, Any] = {
        Trabajo.errores.key: Trabajo.errores + pendientes,
        Trabajo.total.key: trabajo.procesados + pendientes,
        Trabajo.ultimo_error.key: motivo,
    }
    db.execute(update(Trabajo).where(Trabajo.id == trabajo_id).values(valores))
    db.commit()
