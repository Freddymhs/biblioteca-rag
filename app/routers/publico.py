"""API pública, sin API key (tareas 4.3 y 4.4). Lee con el rol público y con límite de uso."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.common.errors import unprocessable
from app.config.constantes import MAX_LARGO_PREGUNTA, MAX_LARGO_SLUG, PATRON_SLUG, UsoPublico
from app.config.database import get_db_publico
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.limites import (
    CuposLLM,
    Limitador,
    ip_cliente,
    obtener_cupos_llm,
    obtener_limitador,
)
from app.providers.llm import obtener_llm
from app.schemas.pregunta import CitaSalida, RespuestaSalida
from app.schemas.publico import (
    MENSAJE_COLECCION_SIN_ESPACIO,
    BusquedaSalida,
    ColeccionPublica,
    PreguntaPublicaEntrada,
)
from app.services import publico
from app.services.publico import Visitante

router = APIRouter(prefix="/publico", tags=["público"])


def limitar_busqueda(request: Request, limitador: Limitador = Depends(obtener_limitador)) -> None:
    limitador.consumir(UsoPublico.BUSQUEDA, ip_cliente(request))


def limitar_respuesta(request: Request, limitador: Limitador = Depends(obtener_limitador)) -> None:
    limitador.consumir(UsoPublico.RESPUESTA, ip_cliente(request))


def visitante_http(
    request: Request,
    limitador: Limitador = Depends(obtener_limitador),
    cupos: CuposLLM = Depends(obtener_cupos_llm),
) -> Visitante:
    return Visitante(ip=ip_cliente(request), limitador=limitador, cupos=cupos)


@router.get(
    "/colecciones",
    response_model=list[ColeccionPublica],
    dependencies=[Depends(limitar_busqueda)],
)
def colecciones(db: Session = Depends(get_db_publico)) -> list[ColeccionPublica]:
    return publico.listar_colecciones_publicas(db)


@router.get("/buscar", response_model=BusquedaSalida, dependencies=[Depends(limitar_busqueda)])
def buscar(
    q: str = Query(min_length=1, max_length=MAX_LARGO_PREGUNTA, examples=["Kc del olivo"]),
    espacio: str | None = Query(default=None, max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG),
    coleccion: str | None = Query(default=None, max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG),
    db: Session = Depends(get_db_publico),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
    visitante: Visitante = Depends(visitante_http),
) -> BusquedaSalida:
    """Fragmentos con cita (documento, páginas, licencia), sin LLM. Nunca el documento completo."""
    if coleccion is not None and espacio is None:
        raise unprocessable(MENSAJE_COLECCION_SIN_ESPACIO)
    citas = publico.buscar_publico(db, q, espacio, coleccion, proveedor, visitante)
    return BusquedaSalida(fragmentos=[CitaSalida.model_validate(asdict(c)) for c in citas])


@router.post(
    "/preguntas", response_model=RespuestaSalida, dependencies=[Depends(limitar_respuesta)]
)
def preguntar(
    datos: PreguntaPublicaEntrada,
    db: Session = Depends(get_db_publico),
    proveedor: ProveedorDeEmbeddings = Depends(obtener_proveedor_embeddings),
    llm: BaseChatModel = Depends(obtener_llm),
    visitante: Visitante = Depends(visitante_http),
) -> RespuestaSalida:
    """Respuesta redactada por el LLM, con cita o «no lo sé». Límite por IP y tope diario."""
    respuesta = publico.preguntar_publico(
        db, datos.pregunta, datos.espacio, datos.coleccion, proveedor, llm, visitante
    )
    return RespuestaSalida.model_validate(asdict(respuesta))
