from dataclasses import asdict

from fastapi import APIRouter, Depends
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.llm import obtener_llm
from app.schemas.pregunta import PreguntaEntrada, RespuestaSalida
from app.services.pregunta import preguntar

router = APIRouter(prefix="/preguntas", tags=["preguntas"])


@router.post("", response_model=RespuestaSalida)
def hacer_pregunta(
    datos: PreguntaEntrada,
    db: Session = Depends(get_db),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
    llm: BaseChatModel = Depends(obtener_llm),
) -> RespuestaSalida:
    respuesta = preguntar(
        db,
        datos.pregunta,
        datos.espacio,
        datos.coleccion,
        proveedor,
        llm,
        settings.PREGUNTA_DISTANCIA_MAXIMA,
    )
    return RespuestaSalida.model_validate(asdict(respuesta))
