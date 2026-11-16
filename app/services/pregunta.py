"""Pregunta → trozos más cercanos (filtrados por espacio/colección y modelo) → respuesta con cita.

Sin trozos bajo la distancia máxima, responde «no lo sé» SIN llamar al LLM.
"""

import re
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import Float, select
from sqlalchemy.orm import Session

from app.config.constantes import MARCA_NO_LO_SE, RESPUESTA_NO_LO_SE, TROZOS_POR_PREGUNTA
from app.models import Coleccion, Documento, Espacio, Trozo
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_pregunta
from app.providers.llm import redactar
from app.services import catalogo

OPERADOR_DISTANCIA_COSENO = "<=>"  # pgvector; es el que acelera el índice HNSW vector_cosine_ops
PATRON_REFERENCIA = re.compile(r"\[(\d+)\]")

INSTRUCCIONES = f"""Eres un asistente que responde SOLO con la información de los fragmentos dados.
- Responde en el idioma de la pregunta, en pocas frases.
- Tras cada afirmación, indica entre corchetes el número del fragmento que la respalda, ej. [1].
- Si los fragmentos no contienen la respuesta, responde exactamente {MARCA_NO_LO_SE} y nada más.
- No uses conocimiento propio ni inventes datos, cifras o fuentes."""


@dataclass(frozen=True)
class Cita:
    documento_id: int
    documento: str
    pagina_inicio: int | None
    pagina_fin: int | None
    fragmento: str
    distancia: float


@dataclass(frozen=True)
class Respuesta:
    respuesta: str
    sabe: bool
    citas: list[Cita]


NO_LO_SE = Respuesta(respuesta=RESPUESTA_NO_LO_SE, sabe=False, citas=[])


def preguntar(
    db: Session,
    pregunta: str,
    espacio: str,
    coleccion: str | None,
    proveedor: ProveedorDeEmbeddings,
    llm: BaseChatModel,
    distancia_maxima: float,
) -> Respuesta:
    _validar_alcance(db, espacio, coleccion)
    vector = embeber_pregunta(proveedor, pregunta)
    candidatas = buscar(db, vector, espacio, coleccion, proveedor.modelo_id)
    relevantes = [cita for cita in candidatas if cita.distancia <= distancia_maxima]
    if not relevantes:
        return NO_LO_SE

    texto = redactar(llm, _mensajes(pregunta, relevantes))
    if MARCA_NO_LO_SE in texto:
        return NO_LO_SE
    return Respuesta(respuesta=texto, sabe=True, citas=_citas_referidas(texto, relevantes))


def buscar(
    db: Session,
    vector: list[float],
    espacio: str,
    coleccion: str | None,
    modelo_id: str,
) -> list[Cita]:
    """Solo trozos del MISMO modelo de embeddings: nunca se comparan vectores de dos modelos."""
    distancia = Trozo.embedding.op(OPERADOR_DISTANCIA_COSENO, return_type=Float)(vector)
    consulta = (
        select(Trozo, Documento.nombre_archivo, distancia.label("distancia"))
        .join(Documento, Trozo.documento_id == Documento.id)
        .join(Coleccion, Documento.coleccion_id == Coleccion.id)
        .join(Espacio, Coleccion.espacio_id == Espacio.id)
        .where(Espacio.slug == espacio, Trozo.embedding_model == modelo_id)
        .order_by(distancia)
        .limit(TROZOS_POR_PREGUNTA)
    )
    if coleccion is not None:
        consulta = consulta.where(Coleccion.slug == coleccion)
    return [
        Cita(
            documento_id=trozo.documento_id,
            documento=nombre,
            pagina_inicio=trozo.pagina_inicio,
            pagina_fin=trozo.pagina_fin,
            fragmento=trozo.texto,
            distancia=valor,
        )
        for trozo, nombre, valor in db.execute(consulta)
    ]


def _validar_alcance(db: Session, espacio: str, coleccion: str | None) -> None:
    """Un espacio o colección inexistente es 404, no «no lo sé»."""
    if coleccion is None:
        catalogo.obtener_espacio(db, espacio)
    else:
        catalogo.obtener_coleccion(db, espacio, coleccion)


def _mensajes(pregunta: str, citas: list[Cita]) -> list[SystemMessage | HumanMessage]:
    fragmentos = "\n\n".join(
        f"[{numero}] {cita.documento}{_paginas_de(cita)}\n{cita.fragmento}"
        for numero, cita in enumerate(citas, start=1)
    )
    return [
        SystemMessage(INSTRUCCIONES),
        HumanMessage(f"Fragmentos:\n\n{fragmentos}\n\nPregunta: {pregunta}"),
    ]


def _paginas_de(cita: Cita) -> str:
    if cita.pagina_inicio is None:
        return ""
    if cita.pagina_inicio == cita.pagina_fin:
        return f", página {cita.pagina_inicio}"
    return f", páginas {cita.pagina_inicio}-{cita.pagina_fin}"


def _citas_referidas(texto: str, citas: list[Cita]) -> list[Cita]:
    """Las que el LLM citó con [n]; si no citó ninguna válida, todas las que se le dieron."""
    numeros = {int(numero) for numero in PATRON_REFERENCIA.findall(texto)}
    referidas = [cita for numero, cita in enumerate(citas, start=1) if numero in numeros]
    return referidas or citas
