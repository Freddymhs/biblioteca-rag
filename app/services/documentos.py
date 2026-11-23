from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.errors import not_found, unprocessable
from app.models import Coleccion, Documento, Trozo
from app.schemas.documento import DocumentoRespuesta


def listar_documentos(db: Session, coleccion: Coleccion) -> list[DocumentoRespuesta]:
    total_trozos = func.count(Trozo.id).label("trozos")
    consulta = (
        select(Documento, total_trozos)
        .outerjoin(Trozo)
        .where(Documento.coleccion_id == coleccion.id)
        .group_by(Documento.id)
        .order_by(Documento.nombre_archivo)
    )
    return [
        DocumentoRespuesta(
            id=documento.id,
            nombre_archivo=documento.nombre_archivo,
            tipo=documento.tipo,
            paginas=documento.paginas,
            trozos=trozos,
            creado_en=documento.creado_en,
            licencia=documento.licencia,
            licencia_verificada=documento.licencia_verificada,
            titulo=documento.titulo,
            fuente=documento.fuente,
            anno=documento.anno,
        )
        for documento, trozos in db.execute(consulta)
    ]


def fijar_licencia(
    db: Session, coleccion: Coleccion, documento_id: int, licencia: str | None, verificada: bool
) -> DocumentoRespuesta:
    """Tarea 4.6: el veredicto lo da una persona; sin licencia no hay nada que verificar."""
    if verificada and not licencia:
        raise unprocessable("Una licencia verificada necesita el nombre de la licencia")
    documento = db.get(Documento, documento_id)
    if documento is None or documento.coleccion_id != coleccion.id:
        raise not_found(f"El documento {documento_id} en «{coleccion.slug}»")
    documento.licencia = licencia
    documento.licencia_verificada = verificada
    db.commit()
    return next(d for d in listar_documentos(db, coleccion) if d.id == documento_id)
