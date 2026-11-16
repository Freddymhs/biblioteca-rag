import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.common.errors import bad_request, payload_too_large
from app.conectores import crear_conector
from app.config.constantes import (
    FUNCION_INGESTAR,
    FUNCION_SINCRONIZAR,
    MAX_BYTES_LOTE,
    MAX_BYTES_SUBIDA,
    TipoTrabajo,
)
from app.config.database import get_db
from app.config.settings import settings
from app.models import Trabajo
from app.providers.cola import ColaArq, obtener_cola
from app.schemas.trabajo import SincronizacionEntrada, TrabajoRespuesta
from app.services import catalogo
from app.services.trabajos import (
    crear_trabajo,
    id_tarea_archivo,
    id_tarea_sincronizacion,
    obtener_trabajo,
)

router = APIRouter(tags=["trabajos"])
BLOQUE_COPIA_BYTES = 1024 * 1024


@router.post(
    "/espacios/{espacio}/colecciones/{coleccion}/lotes",
    response_model=TrabajoRespuesta,
    status_code=status.HTTP_202_ACCEPTED,
)
async def subir_lote(
    espacio: str,
    coleccion: str,
    archivos: list[UploadFile],
    db: Session = Depends(get_db),
    cola: ColaArq = Depends(obtener_cola),
) -> TrabajoRespuesta:
    """Responde en cuanto los archivos quedan en disco y encolados; el avance, en GET /trabajos."""
    if not archivos:
        raise bad_request("El lote no trae archivos")
    destino = await run_in_threadpool(catalogo.obtener_coleccion, db, espacio, coleccion)
    await cola.verificar()  # sin cola el lote no avanzaría: 503 antes de crear o copiar nada
    trabajo = await run_in_threadpool(crear_trabajo, db, destino, TipoTrabajo.LOTE, len(archivos))
    carpeta = settings.INGESTA_TEMPORAL / str(trabajo.id)
    try:
        copias = await run_in_threadpool(_guardar_copias, carpeta, archivos)
        for indice, (ruta, archivo) in enumerate(zip(copias, archivos, strict=True)):
            await cola.encolar(
                FUNCION_INGESTAR,
                trabajo.id,
                str(ruta),
                archivo.filename or "",
                id_tarea=id_tarea_archivo(trabajo.id, indice),
            )
    except BaseException:
        # Cualquier falla desde que existe el trabajo (copia, tope, cola, cancelación) lo
        # descarta con su carpeta: nunca queda un trabajo «pendiente» que nadie va a procesar.
        await run_in_threadpool(_descartar_trabajo, db, trabajo, carpeta)
        raise
    return await run_in_threadpool(respuesta_trabajo, trabajo)


@router.post(
    "/espacios/{espacio}/colecciones/{coleccion}/sincronizaciones",
    response_model=TrabajoRespuesta,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sincronizar(
    espacio: str,
    coleccion: str,
    datos: SincronizacionEntrada,
    db: Session = Depends(get_db),
    cola: ColaArq = Depends(obtener_cola),
) -> TrabajoRespuesta:
    """Re-sync manual: el worker trae los registros y refleja altas, cambios y bajas."""
    crear_conector(datos.conector, settings)  # conector desconocido (422) o sin configurar (503)
    destino = await run_in_threadpool(catalogo.obtener_coleccion, db, espacio, coleccion)
    await cola.verificar()
    trabajo = await run_in_threadpool(crear_trabajo, db, destino, TipoTrabajo.SINCRONIZACION, None)
    try:
        await cola.encolar(
            FUNCION_SINCRONIZAR,
            trabajo.id,
            datos.conector,
            datos.permitir_vaciar,
            id_tarea=id_tarea_sincronizacion(trabajo.id),
        )
    except BaseException:
        await run_in_threadpool(_descartar_trabajo, db, trabajo, None)
        raise
    return await run_in_threadpool(respuesta_trabajo, trabajo)


@router.get("/trabajos/{trabajo_id}", response_model=TrabajoRespuesta)
def consultar_trabajo(trabajo_id: int, db: Session = Depends(get_db)) -> TrabajoRespuesta:
    return respuesta_trabajo(obtener_trabajo(db, trabajo_id))


def _guardar_copias(carpeta: Path, archivos: list[UploadFile]) -> list[Path]:
    """El worker es otro proceso: lee de la carpeta compartida, no de esta petición.

    Cuenta los bytes al copiar: con `Transfer-Encoding: chunked` no hay `Content-Length` y el
    middleware no puede frenar nada; este es el tope real de cada archivo y del lote.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    copias: list[Path] = []
    total_lote = 0
    for indice, archivo in enumerate(archivos):
        ruta = carpeta / f"{indice:05d}"  # el nombre original viaja en la tarea de la cola
        copiados = 0
        with ruta.open("wb") as destino:
            while bloque := archivo.file.read(BLOQUE_COPIA_BYTES):
                copiados += len(bloque)
                total_lote += len(bloque)
                if copiados > MAX_BYTES_SUBIDA:
                    raise payload_too_large(
                        f"«{archivo.filename}» supera el máximo de {MAX_BYTES_SUBIDA} bytes"
                    )
                if total_lote > MAX_BYTES_LOTE:
                    raise payload_too_large(f"El lote supera el máximo de {MAX_BYTES_LOTE} bytes")
                destino.write(bloque)
        copias.append(ruta)
    return copias


def _descartar_trabajo(db: Session, trabajo: Trabajo, carpeta: Path | None) -> None:
    if carpeta is not None:
        shutil.rmtree(carpeta, ignore_errors=True)
    db.rollback()
    db.delete(trabajo)
    db.commit()


def respuesta_trabajo(trabajo: Trabajo) -> TrabajoRespuesta:
    return TrabajoRespuesta(
        id=trabajo.id,
        espacio=trabajo.coleccion.espacio.slug,
        coleccion=trabajo.coleccion.slug,
        tipo=trabajo.tipo,
        estado=trabajo.estado,
        total=trabajo.total,
        procesados=trabajo.procesados,
        ingeridos=trabajo.ingeridos,
        duplicados=trabajo.duplicados,
        sin_cambios=trabajo.sin_cambios,
        rechazados=trabajo.rechazados,
        errores=trabajo.errores,
        eliminados=trabajo.eliminados,
        trozos=trabajo.trozos,
        ultimo_error=trabajo.ultimo_error,
        creado_en=trabajo.creado_en,
        actualizado_en=trabajo.actualizado_en,
    )
