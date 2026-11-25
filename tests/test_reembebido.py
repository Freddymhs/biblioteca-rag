import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constantes import OrigenTrozo
from app.models import Documento, Trozo
from app.services import catalogo
from app.services.ingesta import ingestar
from app.services.reembebido import reembeber_coleccion
from tests.dobles import MODELO_DOBLE, LLMGrabador, proveedor_doble
from tests.pdf_minimo import FIGURA, pdf_minimo

NUEVO = "doble:otro-modelo"
PDF = pdf_minimo(["Riego del olivo\nEl Kc del olivo es 0.65.", FIGURA])


@pytest.fixture(autouse=True)
def biblioteca(db: Session) -> None:
    catalogo.crear_espacio(db, "intereses", "Intereses")
    for coleccion, nombre, contenido in [
        ("agricultura", "olivo.pdf", PDF),
        ("frutales", "pitahaya.txt", b"La cosecha de pitahaya se hace a mano."),
    ]:
        destino = catalogo.crear_coleccion(db, "intereses", coleccion, coleccion)
        vision = LLMGrabador(respuesta="Grafico de potasio")
        ingestar(db, destino, nombre, contenido, proveedor_doble(), vision=vision)


def _trozos(db: Session, coleccion: str) -> list[Trozo]:
    agricultura = catalogo.obtener_coleccion(db, "intereses", coleccion)
    consulta = (
        select(Trozo).join(Documento).where(Documento.coleccion_id == agricultura.id)
    ).order_by(Trozo.orden)
    return list(db.scalars(consulta))


def test_reembebe_todos_los_trozos_con_el_modelo_nuevo_sin_cambiar_textos(db: Session) -> None:
    antes = [(t.texto, t.origen) for t in _trozos(db, "agricultura")]

    resumen = reembeber_coleccion(db, "intereses", "agricultura", proveedor_doble(modelo_id=NUEVO))

    despues = _trozos(db, "agricultura")
    assert (resumen.documentos, resumen.trozos) == (1, len(antes))
    assert {t.embedding_model for t in despues} == {NUEVO}
    assert [(t.texto, t.origen) for t in despues] == antes
    assert OrigenTrozo.VISION in {t.origen for t in despues}  # lo de visión se conserva


def test_correr_dos_veces_no_vuelve_a_embeber(db: Session) -> None:
    reembeber_coleccion(db, "intereses", "agricultura", proveedor_doble(modelo_id=NUEVO))

    segunda = reembeber_coleccion(db, "intereses", "agricultura", proveedor_doble(modelo_id=NUEVO))

    assert (segunda.documentos, segunda.saltados) == (0, 1)


def test_retrocear_vuelve_a_trocear_desde_la_estructura_guardada(db: Session) -> None:
    antes = [(t.texto, t.pagina_inicio) for t in _trozos(db, "agricultura")]

    resumen = reembeber_coleccion(db, "intereses", "agricultura", proveedor_doble(), retrocear=True)

    despues = [(t.texto, t.pagina_inicio) for t in _trozos(db, "agricultura")]
    assert resumen.documentos == 1
    assert despues == antes  # mismo troceador → mismos trozos, visión incluida


def test_retrocear_sin_estructura_guardada_se_salta_y_se_cuenta(db: Session) -> None:
    for documento in db.scalars(select(Documento)):
        documento.estructura = None
    db.commit()

    resumen = reembeber_coleccion(db, "intereses", "agricultura", proveedor_doble(), retrocear=True)

    assert (resumen.documentos, resumen.sin_estructura) == (0, 1)


def test_reembeber_una_coleccion_no_mezcla_modelos_en_la_busqueda_del_espacio(
    client: TestClient, db: Session
) -> None:
    from app.providers.embeddings import obtener_proveedor_embeddings
    from main import app

    reembeber_coleccion(db, "intereses", "frutales", proveedor_doble(modelo_id=NUEVO))
    app.dependency_overrides[obtener_proveedor_embeddings] = lambda: proveedor_doble(
        modelo_id=NUEVO
    )

    respuesta = client.post(
        "/api/preguntas",
        json={"pregunta": "¿Cosecha de pitahaya y riego del olivo?", "espacio": "intereses"},
    )

    documentos = {cita["documento"] for cita in respuesta.json()["citas"]}
    assert documentos == {"pitahaya.txt"}  # olivo.pdf sigue con el modelo viejo: no aparece


def test_coleccion_embebida_con_otro_modelo_avisa_en_vez_de_decir_no_lo_se(
    client: TestClient,
) -> None:
    """B2: sin esto, cambiar de proveedor deja la colección invisible y responde «no lo sé»."""
    from app.providers.embeddings import obtener_proveedor_embeddings
    from main import app

    app.dependency_overrides[obtener_proveedor_embeddings] = lambda: proveedor_doble(
        modelo_id=NUEVO
    )

    respuesta = client.post(
        "/api/preguntas",
        json={"pregunta": "¿Kc del olivo?", "espacio": "intereses", "coleccion": "agricultura"},
    )

    assert respuesta.status_code == 409
    assert MODELO_DOBLE in respuesta.json()["error"]
    assert "app.cli.reembeber" in respuesta.json()["error"]
