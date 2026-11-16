from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models import Extraccion
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.schemas.extraccion import ConfirmacionSalida, FormularioSalida, RechazoSalida
from app.services import dominio

router = APIRouter(prefix="/extracciones", tags=["paquetes de dominio"])


@router.get("/{extraccion_id}/formulario", response_model=FormularioSalida)
def obtener_formulario(extraccion_id: int, db: Session = Depends(get_db)) -> FormularioSalida:
    """El formulario de confirmación: JSON Schema del paquete + lo que propuso el LLM."""
    return FormularioSalida.model_validate(asdict(dominio.formulario(db, extraccion_id)))


@router.post("/{extraccion_id}/confirmacion", response_model=ConfirmacionSalida)
def confirmar(
    extraccion_id: int,
    # `Any`: datos con la forma del esquema del paquete; los valida el servicio.
    datos: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
) -> ConfirmacionSalida:
    """Primera confirmación (pendiente → confirmada). Ya confirmada: 409, se corrige con PUT."""
    return _salida(dominio.confirmar(db, extraccion_id, datos, proveedor))


@router.put("/{extraccion_id}/confirmacion", response_model=ConfirmacionSalida)
def corregir(
    extraccion_id: int,
    # `Any`: datos con la forma del esquema del paquete; los valida el servicio.
    datos: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
) -> ConfirmacionSalida:
    """Corrige una confirmada: datos y trozo se reemplazan juntos. Pendiente: 409."""
    return _salida(dominio.corregir(db, extraccion_id, datos, proveedor))


@router.post("/{extraccion_id}/rechazo", response_model=RechazoSalida)
def rechazar(extraccion_id: int, db: Session = Depends(get_db)) -> RechazoSalida:
    """Descarta una pendiente y su documento. Confirmada: 409 (se corrige, no se rechaza)."""
    rechazo = dominio.rechazar(db, extraccion_id)
    return RechazoSalida(
        extraccion_id=rechazo.extraccion_id,
        documento_id=rechazo.documento_id,
        documento_eliminado=True,
    )


def _salida(extraccion: Extraccion) -> ConfirmacionSalida:
    return ConfirmacionSalida(
        extraccion_id=extraccion.id,
        estado=extraccion.estado,
        trozos=len(extraccion.documento.trozos),
    )
