from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.estructurado import Clasificador, obtener_clasificador
from app.providers.llm import obtener_llm
from app.schemas.pregunta import PreguntaEntrada, RespuestaSalida
from app.services.enrutamiento import responder

router = APIRouter(prefix="/preguntas", tags=["preguntas"])


@router.post("", response_model=RespuestaSalida)
def hacer_pregunta(
    datos: PreguntaEntrada,
    db: Session = Depends(get_db),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
    llm: BaseChatModel = Depends(obtener_llm),
    clasificador: Clasificador = Depends(obtener_clasificador),
) -> RespuestaSalida:
    """En una colección con paquete de dominio, un cálculo va por SQL fijo; si no, semántica."""
    respuesta = responder(
        db,
        datos.pregunta,
        datos.espacio,
        datos.coleccion,
        proveedor,
        llm,
        clasificador,
        settings.PREGUNTA_DISTANCIA_MAXIMA,
        hoy=date.today(),
    )
    return RespuestaSalida.model_validate(asdict(respuesta))
