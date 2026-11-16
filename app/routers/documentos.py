from collections.abc import Callable

from fastapi import APIRouter, Depends, UploadFile, status
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config.constantes import MAX_BYTES_SUBIDA
from app.config.database import get_db
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.estructurado import Extractor, obtener_fabrica_extractor
from app.providers.vision import obtener_vision
from app.schemas.documento import DocumentoIngerido, DocumentoRespuesta
from app.services import catalogo
from app.services.documentos import listar_documentos
from app.services.ingesta import DocumentoPorConfirmar, ingestar, ingestar_con_paquete

router = APIRouter(
    prefix="/espacios/{espacio}/colecciones/{coleccion}/documentos", tags=["documentos"]
)


# `def` y no `async def`: la extracción es CPU pesada y FastAPI la corre en un hilo aparte.
@router.post("", response_model=DocumentoIngerido, status_code=status.HTTP_201_CREATED)
def subir_documento(
    espacio: str,
    coleccion: str,
    archivo: UploadFile,
    db: Session = Depends(get_db),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
    vision: BaseChatModel | None = Depends(obtener_vision),
    fabrica_extractor: Callable[[], Extractor] = Depends(obtener_fabrica_extractor),
) -> DocumentoIngerido:
    destino = catalogo.obtener_coleccion(db, espacio, coleccion)
    # Un byte de más basta para que la detección rechace lo que supera el máximo.
    contenido = archivo.file.read(MAX_BYTES_SUBIDA + 1)
    nombre = archivo.filename or ""  # el servicio pone el nombre por defecto
    if destino.paquete is not None:
        extractor = fabrica_extractor()  # solo aquí: sin paquete no hace falta un LLM
        return _por_confirmar(ingestar_con_paquete(db, destino, nombre, contenido, extractor))
    resultado = ingestar(db, destino, nombre, contenido, proveedor, vision=vision)
    documento = resultado.documento
    return DocumentoIngerido(
        id=documento.id,
        nombre_archivo=documento.nombre_archivo,
        tipo=documento.tipo,
        paginas=documento.paginas,
        trozos=resultado.trozos,
        creado_en=documento.creado_en,
        paginas_sin_texto=resultado.paginas_sin_texto,
        paginas_por_vision=resultado.paginas_por_vision,
        paginas_en_blanco=resultado.paginas_en_blanco,
        paginas_sin_indexar=resultado.paginas_sin_indexar,
    )


def _por_confirmar(pendiente: DocumentoPorConfirmar) -> DocumentoIngerido:
    documento = pendiente.documento
    return DocumentoIngerido(
        id=documento.id,
        nombre_archivo=documento.nombre_archivo,
        tipo=documento.tipo,
        paginas=documento.paginas,
        trozos=0,  # nada se embebe hasta confirmar
        creado_en=documento.creado_en,
        extraccion_id=pendiente.extraccion.id,
        paginas_sin_texto=[],
        paginas_por_vision=[],
        paginas_en_blanco=[],
        paginas_sin_indexar=[],
    )


@router.get("", response_model=list[DocumentoRespuesta])
def listar(espacio: str, coleccion: str, db: Session = Depends(get_db)) -> list[DocumentoRespuesta]:
    return listar_documentos(db, catalogo.obtener_coleccion(db, espacio, coleccion))
