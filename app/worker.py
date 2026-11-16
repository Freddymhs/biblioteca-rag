"""Worker de arq: ingesta y sincronización en segundo plano, y barrido de trabajos huérfanos.

No emite trazas (I9): la FASE_5 traza preguntas; la ingesta en segundo plano no configura un
proveedor de OpenTelemetry, así que sus etapas (visión incluida) se crean y se descartan.

    uv run arq app.worker.WorkerSettings

`max_jobs = 1`: Docling se serializa igual (candado) y dos conversiones a la vez duplican su
memoria. `max_tries = 1`, medido el 2026-11-16 con Redis real: si el worker muere a mitad de una
tarea, arq NO vuelve a correrla (la marca «max retries exceeded» al vencer su `job_timeout`).
Con 2 intentos sí la repetiría, pero un archivo ya guardado y contado se contaría dos veces.
Lo que una muerte deja a medias lo cierra el barrido: un trabajo sin terminar, más viejo que la
gracia y sin ninguna tarea viva en Redis cuenta lo que le faltaba como error, con el motivo.
"""

import asyncio
import shutil
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from arq import cron, func
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorProveedor
from app.common.logger import logger
from app.conectores import crear_conector
from app.conectores.base import Conector
from app.config.constantes import (
    FUNCION_BARRER,
    FUNCION_INGESTAR,
    FUNCION_SINCRONIZAR,
    MAX_BYTES_SUBIDA,
    MINUTOS_DEL_BARRIDO,
    TIMEOUT_TRABAJO_ARCHIVO_SEGUNDOS,
)
from app.config.database import SessionLocal
from app.config.settings import settings
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.vision import obtener_vision
from app.services.ingesta_por_lotes import Resultado, ResultadoArchivo, ingestar_en_lote
from app.services.sincronizacion import sincronizar_coleccion
from app.services.trabajos import (
    cerrar_con_error,
    cerrar_huerfano,
    finalizar_sincronizacion,
    ids_de_tareas,
    obtener_trabajo,
    sumar_resultado,
    trabajos_vencidos,
)

AbrirSesion = Callable[[], AbstractContextManager[Session]]
MOTIVO_HUERFANO = (
    "Trabajo interrumpido: el worker se detuvo o la cola perdió sus tareas. "
    "Lo que faltaba se cuenta como error; volver a subir esos archivos."
)
# Una tarea en alguno de estos estados todavía puede correr: el trabajo no es huérfano.
ESTADOS_VIVOS = {JobStatus.deferred, JobStatus.queued, JobStatus.in_progress}


class CopiaInvalida(Exception):
    """La ruta recibida por Redis no es una copia de lote utilizable."""

    def __init__(self, resultado: Resultado, motivo: str, borrar: bool) -> None:
        super().__init__(motivo)
        self.resultado = resultado
        self.motivo = motivo
        self.borrar = borrar  # solo se borra lo que está dentro de la carpeta temporal


def procesar_archivo(
    abrir_sesion: AbrirSesion,
    obtener_proveedor: Callable[[], ProveedorDeEmbeddings],
    obtener_vision_: Callable[[], BaseChatModel | None],
    trabajo_id: int,
    ruta: Path,
    nombre: str,
) -> ResultadoArchivo:
    """Ingiere un archivo del lote y lo cuenta. Cualquier falla también se cuenta (como error)."""
    prefijo = f"[trabajo {trabajo_id}] {nombre}"
    borrar = _es_copia_del_lote(ruta)
    try:
        contenido = _leer_copia(ruta)
        with abrir_sesion() as db:
            trabajo = obtener_trabajo(db, trabajo_id)
            espacio, coleccion = trabajo.coleccion.espacio.slug, trabajo.coleccion.slug
            db.commit()
            return ingestar_en_lote(
                db,
                espacio,
                coleccion,
                nombre,
                contenido,
                obtener_proveedor(),
                obtener_vision_(),
                prefijo,
                contar=lambda db_, archivo: sumar_resultado(db_, trabajo_id, archivo),
            )
    except CopiaInvalida as error:
        logger.error(f"{prefijo}: {error.motivo}")
        archivo = ResultadoArchivo(error.resultado, 0, error.motivo)
    except AppError as error:  # 503: proveedor sin configurar · 404: el trabajo no existe
        logger.error(f"{prefijo}: {error.message}")
        archivo = ResultadoArchivo(Resultado.ERROR, 0, error.message)
    except Exception as error:
        logger.exception(f"{prefijo}: error inesperado")
        archivo = ResultadoArchivo(Resultado.ERROR, 0, f"error inesperado: {error!r}")
    finally:
        if borrar:
            _borrar_copia(ruta)
    _contar_aparte(abrir_sesion, trabajo_id, archivo, prefijo)
    return archivo


def _es_copia_del_lote(ruta: Path) -> bool:
    return ruta.resolve().is_relative_to(settings.INGESTA_TEMPORAL.resolve())


def _leer_copia(ruta: Path) -> bytes:
    """La ruta llega por Redis: se valida antes de leerla, y el tamaño antes de cargarla."""
    if not _es_copia_del_lote(ruta):
        raise CopiaInvalida(
            Resultado.ERROR, f"ruta fuera de la carpeta temporal: {ruta}", borrar=False
        )
    tamano = ruta.stat().st_size  # FileNotFoundError si la copia no está: cae en el caso general
    if tamano > MAX_BYTES_SUBIDA:
        raise CopiaInvalida(
            Resultado.RECHAZADO,
            f"El archivo supera el máximo de {MAX_BYTES_SUBIDA} bytes",
            borrar=True,
        )
    return ruta.read_bytes()


def _contar_aparte(
    abrir_sesion: AbrirSesion, trabajo_id: int, archivo: ResultadoArchivo, prefijo: str
) -> None:
    """La falla ocurrió fuera de `ingestar_en_lote`: se cuenta en una transacción propia."""
    try:
        with abrir_sesion() as db:
            db.rollback()
            sumar_resultado(db, trabajo_id, archivo)
            db.commit()
    except Exception:
        # Si ni siquiera se puede contar (la base cayó), el barrido lo cerrará como huérfano.
        logger.exception(f"{prefijo}: no se pudo contar el resultado")


def procesar_sincronizacion(
    abrir_sesion: AbrirSesion,
    obtener_proveedor: Callable[[], ProveedorDeEmbeddings],
    crear_conector_: Callable[[str], Conector],
    trabajo_id: int,
    conector: str,
    permitir_vaciar: bool = False,
) -> None:
    with abrir_sesion() as db:
        trabajo = obtener_trabajo(db, trabajo_id)
        espacio, coleccion = trabajo.coleccion.espacio.slug, trabajo.coleccion.slug
        db.commit()
        try:
            resumen = sincronizar_coleccion(
                db,
                espacio,
                coleccion,
                crear_conector_(conector),
                obtener_proveedor(),
                contar=lambda db_, archivo: sumar_resultado(db_, trabajo_id, archivo),
                permitir_vaciar=permitir_vaciar,
            )
        except (AppError, ErrorProveedor) as error:
            mensaje = error.message if isinstance(error, AppError) else str(error)
            logger.error(f"[trabajo {trabajo_id}] sincronización con «{conector}»: {mensaje}")
            cerrar_con_error(db, trabajo_id, mensaje)
            return
        # Total y bajas al final y juntos: antes, el trabajo se veía terminado sin las bajas.
        finalizar_sincronizacion(db, trabajo_id, resumen.procesados, resumen.eliminados)
        logger.info(f"[trabajo {trabajo_id}] {conector} → {espacio}/{coleccion}: {resumen}")


def _borrar_copia(ruta: Path) -> None:
    ruta.unlink(missing_ok=True)
    carpeta = ruta.parent
    if carpeta.exists() and not any(carpeta.iterdir()):
        carpeta.rmdir()  # el último archivo del lote se lleva la carpeta del trabajo


# `Any`: el contexto de arq es un dict libre que el worker comparte entre tareas.
async def ingestar_archivo(ctx: dict[str, Any], trabajo_id: int, ruta: str, nombre: str) -> str:
    archivo = await asyncio.to_thread(
        procesar_archivo,
        ctx["abrir_sesion"],
        ctx["obtener_proveedor"],
        ctx["obtener_vision"],
        trabajo_id,
        Path(ruta),
        nombre,
    )
    return archivo.resultado.value


async def sincronizar_en_cola(
    ctx: dict[str, Any], trabajo_id: int, conector: str, permitir_vaciar: bool = False
) -> None:
    await asyncio.to_thread(
        procesar_sincronizacion,
        ctx["abrir_sesion"],
        ctx["obtener_proveedor"],
        ctx["crear_conector"],
        trabajo_id,
        conector,
        permitir_vaciar,
    )


async def barrer_trabajos_huerfanos(ctx: dict[str, Any]) -> int:
    """Cierra los trabajos sin terminar a los que ya no les queda ninguna tarea viva en Redis."""
    redis: ArqRedis = ctx["redis"]
    candidatos = await asyncio.to_thread(_candidatos, ctx["abrir_sesion"])
    cerrados = 0
    for trabajo_id, tareas in candidatos:
        estados = [await Job(tarea, redis).status() for tarea in tareas]
        if any(estado in ESTADOS_VIVOS for estado in estados):
            continue
        await asyncio.to_thread(_cerrar_huerfano, ctx["abrir_sesion"], trabajo_id)
        cerrados += 1
    if cerrados:
        logger.warning(f"Barrido: {cerrados} trabajos huérfanos cerrados como error")
    return cerrados


def _candidatos(abrir_sesion: AbrirSesion) -> list[tuple[int, list[str]]]:
    with abrir_sesion() as db:
        return [(trabajo.id, ids_de_tareas(trabajo)) for trabajo in trabajos_vencidos(db)]


def _cerrar_huerfano(abrir_sesion: AbrirSesion, trabajo_id: int) -> None:
    with abrir_sesion() as db:
        cerrar_huerfano(db, trabajo_id, MOTIVO_HUERFANO)
    shutil.rmtree(settings.INGESTA_TEMPORAL / str(trabajo_id), ignore_errors=True)


async def al_arrancar(ctx: dict[str, Any]) -> None:
    """`setdefault`: los tests inyectan sus dobles por el mismo `ctx`."""
    ctx.setdefault("abrir_sesion", SessionLocal)
    ctx.setdefault("obtener_proveedor", obtener_proveedor_embeddings)
    ctx.setdefault("obtener_vision", obtener_vision)
    ctx.setdefault("crear_conector", lambda nombre: crear_conector(nombre, settings))


class WorkerSettings:
    functions = [
        func(ingestar_archivo, name=FUNCION_INGESTAR),
        func(sincronizar_en_cola, name=FUNCION_SINCRONIZAR),
    ]
    cron_jobs = [
        cron(
            barrer_trabajos_huerfanos,
            name=FUNCION_BARRER,
            minute=MINUTOS_DEL_BARRIDO,
            run_at_startup=True,
        )
    ]
    on_startup = al_arrancar
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 1
    max_tries = 1
    job_timeout = TIMEOUT_TRABAJO_ARCHIVO_SEGUNDOS
