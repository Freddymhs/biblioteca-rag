from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
        )
        for documento, trozos in db.execute(consulta)
    ]
