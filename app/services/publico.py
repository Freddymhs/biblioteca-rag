"""Lo que ve cualquiera (tarea 4.3): colecciones públicas y fragmentos con cita, sin LLM.

Corre con la sesión del rol público: el RLS de Postgres deja fuera lo privado y lo que no tiene
licencia verificada. Las consultas además lo filtran (defensa en profundidad, ver `buscar`).
"""

from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.config.constantes import AtributoTraza, EtapaTraza, UsoPublico
from app.config.settings import settings
from app.models import Coleccion, Documento, Espacio
from app.observabilidad import anotar, etapa
from app.providers.embeddings import ProveedorDeEmbeddings, embeber_pregunta
from app.providers.limites import CuposLLM, Limitador
from app.schemas.publico import ColeccionPublica
from app.services.pregunta import (
    Cita,
    Respuesta,
    anotar_alcance,
    avisar_si_esta_embebida_con_otro_modelo,
    buscar,
    ids_de_trozos,
    preguntar,
    validar_alcance,
)


def listar_colecciones_publicas(db: Session) -> list[ColeccionPublica]:
    documentos_publicos = and_(
        Documento.coleccion_id == Coleccion.id, Documento.licencia_verificada
    )
    consulta = (
        select(Espacio.slug, Coleccion.slug, Coleccion.nombre, func.count(Documento.id))
        .join(Coleccion, Coleccion.espacio_id == Espacio.id)
        .outerjoin(Documento, documentos_publicos)
        .where(Coleccion.publica)
        .group_by(Espacio.slug, Coleccion.slug, Coleccion.nombre)
        .order_by(Espacio.slug, Coleccion.slug)
    )
    return [
        ColeccionPublica(espacio=espacio, slug=slug, nombre=nombre, documentos=documentos)
        for espacio, slug, nombre, documentos in db.execute(consulta)
    ]


@dataclass(frozen=True)
class Visitante:
    """Quién pide y con qué se le cobra; lo arman la API pública y el MCP por igual."""

    ip: str
    limitador: Limitador
    cupos: CuposLLM


def buscar_publico(
    db: Session,
    texto: str,
    espacio: str | None,
    coleccion: str | None,
    proveedor: ProveedorDeEmbeddings,
    visitante: Visitante,
) -> list[Cita]:
    """Los fragmentos bajo la distancia máxima: el mismo criterio que la respuesta redactada.
    La cuota diaria se gasta recién validado el alcance (un 404 no la gasta, G2)."""
    with etapa(EtapaTraza.BUSCAR_PUBLICO, {AtributoTraza.PREGUNTA_LARGO: len(texto)}):
        citas = _buscar_publico(db, texto, espacio, coleccion, proveedor, visitante)
        anotar({AtributoTraza.TROZOS_USADOS: ids_de_trozos(citas)})
    visitante.limitador.contar_servida(UsoPublico.BUSQUEDA)
    return citas


def _buscar_publico(
    db: Session,
    texto: str,
    espacio: str | None,
    coleccion: str | None,
    proveedor: ProveedorDeEmbeddings,
    visitante: Visitante,
) -> list[Cita]:
    validar_alcance(db, espacio, coleccion)
    anotar_alcance(espacio, coleccion)
    visitante.limitador.reservar_cuota_diaria(UsoPublico.BUSQUEDA, visitante.ip)
    vector = embeber_pregunta(proveedor, texto)
    candidatas = buscar(db, vector, espacio, coleccion, proveedor.modelo_id, solo_publico=True)
    if not candidatas:
        avisar_si_esta_embebida_con_otro_modelo(
            db, espacio, coleccion, proveedor.modelo_id, solo_publico=True
        )
    return [cita for cita in candidatas if cita.distancia <= settings.PREGUNTA_DISTANCIA_MAXIMA]


def preguntar_publico(
    db: Session,
    pregunta: str,
    espacio: str | None,
    coleccion: str | None,
    proveedor: ProveedorDeEmbeddings,
    llm: BaseChatModel,
    visitante: Visitante,
) -> Respuesta:
    """Respuesta redactada solo con lo público. Orden: alcance válido → cupo del LLM (G4) →
    cuota diaria (G2) → embeber y redactar. Sin cupo, ni la cuota se gasta."""
    validar_alcance(db, espacio, coleccion)
    with visitante.cupos.ocupar():
        visitante.limitador.reservar_cuota_diaria(UsoPublico.RESPUESTA, visitante.ip)
        respuesta = preguntar(
            db,
            pregunta,
            espacio,
            coleccion,
            proveedor,
            llm,
            settings.PREGUNTA_DISTANCIA_MAXIMA,
            solo_publico=True,
        )
    visitante.limitador.contar_servida(UsoPublico.RESPUESTA)
    return respuesta
