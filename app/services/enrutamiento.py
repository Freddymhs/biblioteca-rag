"""Enrutamiento de preguntas con LangGraph (tarea 3.2): «cálculo» o «significado».

    clasificar ──(herramienta válida)──▶ calcular  (SQL fijo, respuesta determinista)
         └──────(cualquier otra cosa)──▶ buscar    (búsqueda semántica + LLM con cita)

Solo se clasifica dentro de una colección con paquete de dominio. El clasificador elige el nombre
de una herramienta y propone argumentos; nada llega al SQL sin pasar por el modelo Pydantic de la
herramienta. Una decisión inválida cae en la búsqueda semántica: nunca un cálculo inventado.
"""

from datetime import date
from typing import NotRequired, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.logger import logger
from app.config.constantes import (
    MAX_CITAS_CALCULO,
    AtributoTraza,
    EtapaTraza,
    OrigenTrozo,
    RutaRespuesta,
    TipoDecision,
)
from app.dominio import obtener_paquete
from app.dominio.base import HerramientaSQL, PaqueteDominio
from app.models import Coleccion, Documento, Trozo
from app.observabilidad import anotar, etapa
from app.providers.embeddings import ProveedorDeEmbeddings
from app.providers.estructurado import Clasificador, Decision
from app.services import catalogo
from app.services.pregunta import Cita, Respuesta, ids_de_trozos, preguntar, titulo_visible

NODO_CLASIFICAR = "clasificar"
NODO_CALCULAR = "calcular"
NODO_BUSCAR = "buscar"
DISTANCIA_DATO_EXACTO = 0.0  # una cita de la ruta SQL no viene de una búsqueda por cercanía


class EstadoGrafo(TypedDict):
    pregunta: str
    operacion: NotRequired[tuple[HerramientaSQL, BaseModel] | None]
    respuesta: NotRequired[Respuesta]


class Actualizacion(TypedDict, total=False):
    """Lo que devuelve cada nodo: LangGraph lo mezcla en el estado."""

    operacion: tuple[HerramientaSQL, BaseModel] | None
    respuesta: Respuesta


def responder(
    db: Session,
    pregunta: str,
    espacio: str,
    coleccion: str | None,
    proveedor: ProveedorDeEmbeddings,
    llm: BaseChatModel,
    clasificador: Clasificador,
    distancia_maxima: float,
    hoy: date,
) -> Respuesta:
    destino = catalogo.obtener_coleccion(db, espacio, coleccion) if coleccion else None
    paquete = obtener_paquete(destino.paquete) if destino and destino.paquete else None
    if destino is None or paquete is None or not paquete.herramientas:
        return preguntar(db, pregunta, espacio, coleccion, proveedor, llm, distancia_maxima)

    # El parámetro se llama `state`: el protocolo de nodos de LangGraph lo exige por nombre.
    def clasificar(state: EstadoGrafo) -> Actualizacion:
        with etapa(EtapaTraza.CLASIFICAR):
            decision = clasificador(state["pregunta"], paquete, hoy)
            operacion = _calculo_valido(decision, paquete)
            # I6: el nombre que propone el LLM es texto libre; a la traza va solo si es una
            # herramienta del paquete (la validada), y la decisión, que es un enum.
            herramienta = operacion[0].nombre if operacion is not None else None
            anotar(
                {
                    AtributoTraza.DECISION: decision.tipo.value,
                    AtributoTraza.HERRAMIENTA: herramienta,
                }
            )
            return {"operacion": operacion}

    def calcular(state: EstadoGrafo) -> Actualizacion:
        return {"respuesta": _calcular(db, destino, state)}

    def buscar(state: EstadoGrafo) -> Actualizacion:
        semantica = preguntar(
            db, state["pregunta"], espacio, coleccion, proveedor, llm, distancia_maxima
        )
        return {"respuesta": semantica}

    constructor = StateGraph(EstadoGrafo)
    constructor.add_node(NODO_CLASIFICAR, clasificar)
    constructor.add_node(NODO_CALCULAR, calcular)
    constructor.add_node(NODO_BUSCAR, buscar)
    constructor.add_edge(START, NODO_CLASIFICAR)
    constructor.add_conditional_edges(
        NODO_CLASIFICAR,
        _siguiente,
        {NODO_CALCULAR: NODO_CALCULAR, NODO_BUSCAR: NODO_BUSCAR},
    )
    constructor.add_edge(NODO_CALCULAR, END)
    constructor.add_edge(NODO_BUSCAR, END)
    resultado = constructor.compile().invoke({"pregunta": pregunta})
    return resultado["respuesta"]


def _siguiente(estado: EstadoGrafo) -> str:
    return NODO_CALCULAR if estado.get("operacion") else NODO_BUSCAR


def _calculo_valido(
    decision: Decision, paquete: PaqueteDominio
) -> tuple[HerramientaSQL, BaseModel] | None:
    if decision.tipo != TipoDecision.CALCULO or decision.herramienta is None:
        return None
    herramienta = paquete.herramienta(decision.herramienta)
    if herramienta is None:
        logger.warning(f"Clasificador eligió una herramienta inexistente: {decision.herramienta!r}")
        return None
    try:
        argumentos = herramienta.argumentos.model_validate(decision.argumentos)
    except ValidationError as error:
        logger.warning(f"Argumentos inválidos para {herramienta.nombre}: {error}")
        return None
    return herramienta, argumentos


def _calcular(db: Session, destino: Coleccion, estado: EstadoGrafo) -> Respuesta:
    operacion = estado.get("operacion")
    if operacion is None:  # el borde condicional solo llega aquí con un cálculo válido
        raise RuntimeError("Nodo calcular sin cálculo: el borde condicional está mal")
    herramienta, argumentos = operacion
    with etapa(EtapaTraza.CALCULAR, {AtributoTraza.HERRAMIENTA: herramienta.nombre}):
        resultado = herramienta.ejecutar(db, destino.id, paquete_de(destino), argumentos)
        citas = _citas_de_datos(db, resultado.documento_ids)
        anotar({AtributoTraza.TROZOS_USADOS: ids_de_trozos(citas)})
    return Respuesta(
        respuesta=resultado.respuesta + _aviso_de_citas(len(citas), len(resultado.documento_ids)),
        # Sin filas no hay datos confirmados que respalden nada: el formateador lo dice y no «sabe».
        sabe=bool(resultado.documento_ids),
        citas=citas,
        ruta=RutaRespuesta.SQL,
        herramienta=herramienta.nombre,
    )


def paquete_de(destino: Coleccion) -> str:
    if destino.paquete is None:  # la ruta de cálculo solo existe para colecciones con paquete
        raise RuntimeError(f"La colección {destino.slug} no tiene paquete")
    return destino.paquete


def _aviso_de_citas(mostradas: int, total: int) -> str:
    if mostradas == total:
        return ""
    return f" (Se citan {mostradas} de {total} documentos.)"


def _citas_de_datos(db: Session, documento_ids: list[int]) -> list[Cita]:
    """Los documentos que respaldan el cálculo, con sus datos confirmados como fragmento; a lo
    más MAX_CITAS_CALCULO (F1): el total lo da la respuesta, no la lista."""
    if not documento_ids:
        return []
    consulta = (
        select(Trozo, Documento.nombre_archivo, Documento.titulo, Documento.fuente, Documento.anno)
        .join(Documento, Trozo.documento_id == Documento.id)
        .where(Trozo.documento_id.in_(documento_ids), Trozo.origen == OrigenTrozo.DATOS)
        .order_by(Documento.nombre_archivo)
        .limit(MAX_CITAS_CALCULO)
    )
    return [
        Cita(
            documento_id=trozo.documento_id,
            documento=nombre,
            pagina_inicio=None,
            pagina_fin=None,
            origen=OrigenTrozo.DATOS,
            fragmento=trozo.texto,
            distancia=DISTANCIA_DATO_EXACTO,
            trozo_id=trozo.id,
            titulo=titulo_visible(titulo, nombre),
            fuente=fuente,
            anno=anno,
        )
        for trozo, nombre, titulo, fuente, anno in db.execute(consulta)
    ]
