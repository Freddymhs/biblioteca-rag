"""Confirmación de extracciones (tarea 3.1): lo confirmado, y solo eso, se embebe."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.errors import conflict, not_found, unprocessable
from app.config.constantes import EstadoExtraccion, OrigenTrozo
from app.dominio import obtener_paquete
from app.models import Documento, Extraccion, Trozo
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_documentos


@dataclass(frozen=True)
class Formulario:
    extraccion_id: int
    documento_id: int
    documento: str
    paquete: str
    estado: EstadoExtraccion
    # `Any`: el JSON Schema del paquete y los datos con su forma (lo que muestra el formulario).
    json_schema: dict[str, Any]
    propuesta: dict[str, Any]
    errores: list[str]
    confirmados: dict[str, Any] | None


def obtener_extraccion(db: Session, extraccion_id: int) -> Extraccion:
    extraccion = db.get(Extraccion, extraccion_id)
    if extraccion is None:
        raise not_found(f"La extracción {extraccion_id}")
    return extraccion


def formulario(db: Session, extraccion_id: int) -> Formulario:
    extraccion = obtener_extraccion(db, extraccion_id)
    paquete = obtener_paquete(extraccion.paquete)
    return Formulario(
        extraccion_id=extraccion.id,
        documento_id=extraccion.documento_id,
        documento=extraccion.documento.nombre_archivo,
        paquete=paquete.nombre,
        estado=extraccion.estado,
        json_schema=paquete.esquema.model_json_schema(),
        propuesta=extraccion.propuesta,
        errores=extraccion.errores,
        confirmados=extraccion.confirmados,
    )


@dataclass(frozen=True)
class Rechazo:
    extraccion_id: int
    documento_id: int


# `Any`: lo que envía la persona; se valida contra el esquema del paquete antes de tocar nada.
def confirmar(
    db: Session, extraccion_id: int, datos: dict[str, Any], proveedor: ProveedorDeEmbeddings
) -> Extraccion:
    """Primera confirmación de una extracción pendiente."""
    return _aplicar(db, extraccion_id, datos, proveedor, esperado=EstadoExtraccion.PENDIENTE)


def corregir(
    db: Session, extraccion_id: int, datos: dict[str, Any], proveedor: ProveedorDeEmbeddings
) -> Extraccion:
    """Corrección de una ya confirmada: reemplaza datos y trozo en una transacción."""
    return _aplicar(db, extraccion_id, datos, proveedor, esperado=EstadoExtraccion.CONFIRMADA)


def rechazar(db: Session, extraccion_id: int) -> Rechazo:
    """Descarta una propuesta: borra el documento (y su extracción), así el archivo puede volver a
    subirse. Una confirmada no se rechaza: se corrige."""
    extraccion = _bloquear(db, extraccion_id)
    if extraccion.estado != EstadoExtraccion.PENDIENTE:
        raise conflict(f"La extracción {extraccion_id} no está pendiente: corregirla con PUT")
    rechazo = Rechazo(extraccion_id=extraccion.id, documento_id=extraccion.documento_id)
    db.delete(extraccion.documento)  # cascada: la extracción se va con el documento
    db.commit()
    return rechazo


def _aplicar(
    db: Session,
    extraccion_id: int,
    datos: dict[str, Any],
    proveedor: ProveedorDeEmbeddings,
    esperado: EstadoExtraccion,
) -> Extraccion:
    extraccion = obtener_extraccion(db, extraccion_id)
    _exigir_estado(extraccion, esperado)
    paquete = obtener_paquete(extraccion.paquete)
    try:
        validados = paquete.esquema.model_validate(datos)
    except ValidationError as error:
        raise unprocessable(f"Datos inválidos para «{paquete.nombre}»: {error}") from error
    texto = paquete.texto_para_embeber(validados)
    db.commit()  # embeber va a la red: sin transacción abierta mientras tanto

    vector = embeber_documentos(proveedor, [texto])[0]
    # Se relee CON BLOQUEO y se vuelve a comprobar: otra petición pudo confirmar mientras se
    # embebía. Sin esto, dos confirmaciones simultáneas pasaban y la segunda pisaba la primera.
    extraccion = _bloquear(db, extraccion_id)
    _exigir_estado(extraccion, esperado)
    documento: Documento = extraccion.documento
    extraccion.confirmados = validados.model_dump(mode="json")
    extraccion.estado = EstadoExtraccion.CONFIRMADA
    extraccion.confirmado_en = datetime.now(UTC)
    documento.trozos = [
        Trozo(
            orden=0,
            texto=texto,
            pagina_inicio=None,
            pagina_fin=None,
            origen=OrigenTrozo.DATOS,
            embedding=vector,
            embedding_model=proveedor.modelo_id,
        )
    ]
    db.commit()  # datos confirmados y su trozo: los dos o ninguno
    db.refresh(extraccion)
    return extraccion


def _bloquear(db: Session, extraccion_id: int) -> Extraccion:
    consulta = select(Extraccion).where(Extraccion.id == extraccion_id).with_for_update()
    extraccion = db.scalars(consulta.execution_options(populate_existing=True)).one_or_none()
    if extraccion is None:
        raise not_found(f"La extracción {extraccion_id}")
    return extraccion


def _exigir_estado(extraccion: Extraccion, esperado: EstadoExtraccion) -> None:
    if extraccion.estado == esperado:
        return
    if esperado == EstadoExtraccion.PENDIENTE:
        raise conflict(f"La extracción {extraccion.id} ya está confirmada: corregirla con PUT")
    raise conflict(f"La extracción {extraccion.id} no está confirmada: confirmarla con POST")
