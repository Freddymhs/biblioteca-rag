import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.constantes import MARCA_NO_LO_SE, RESPUESTA_NO_LO_SE, OrigenTrozo
from app.services import catalogo
from app.services.ingesta import ingestar
from tests.dobles import LLMGrabador, RespuestaHTTP, proveedor_doble
from tests.pdf_minimo import FIGURA, pdf_minimo

URL = "/api/preguntas"
PDF_OLIVO = pdf_minimo(["Riego del olivo\nEl Kc del olivo es 0.65.", "", "Poda del olivo"])
TXT_PITAHAYA = b"La cosecha de pitahaya se hace a mano."
TXT_POTASIO = b"Fertilizacion con potasio en el olivo."


@pytest.fixture(autouse=True)
def biblioteca(db: Session) -> None:
    """intereses/agricultura: olivo.pdf · intereses/frutales: pitahaya.txt ·
    personal/notas: potasio."""
    proveedor = proveedor_doble()
    catalogo.crear_espacio(db, "intereses", "Intereses")
    catalogo.crear_espacio(db, "personal", "Personal")
    for espacio, coleccion, nombre, contenido in [
        ("intereses", "agricultura", "olivo.pdf", PDF_OLIVO),
        ("intereses", "frutales", "pitahaya.txt", TXT_PITAHAYA),
        ("personal", "notas", "potasio.txt", TXT_POTASIO),
    ]:
        destino = catalogo.crear_coleccion(db, espacio, coleccion, coleccion)
        ingestar(db, destino, nombre, contenido, proveedor, vision=None)


def _preguntar(
    client: TestClient, pregunta: str, espacio: str, coleccion: str | None = None
) -> RespuestaHTTP:
    cuerpo = {"pregunta": pregunta, "espacio": espacio, "coleccion": coleccion}
    return client.post(URL, json=cuerpo)


def test_respuesta_con_cita_de_documento_y_pagina(client: TestClient, llm: LLMGrabador) -> None:
    respuesta = _preguntar(client, "¿Cuál es el Kc del olivo?", "intereses", "agricultura")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["sabe"] is True
    assert cuerpo["respuesta"] == "El Kc del olivo es 0.65 [1]."
    cita = cuerpo["citas"][0]
    assert (cita["documento"], cita["pagina_inicio"], cita["pagina_fin"]) == ("olivo.pdf", 1, 1)
    assert len(cuerpo["citas"]) == 1  # el LLM citó solo [1]
    prompt = llm.recibidos[0][-1].text
    assert "[1] olivo.pdf, página 1" in prompt
    assert "0.65" in prompt


def test_sin_contexto_relevante_dice_no_lo_se_sin_llamar_al_llm(
    client: TestClient, llm: LLMGrabador
) -> None:
    respuesta = _preguntar(client, "¿Cómo se hornea el pan?", "intereses", "agricultura")

    assert respuesta.json() == {
        "respuesta": RESPUESTA_NO_LO_SE,
        "sabe": False,
        "citas": [],
        "ruta": "semantica",
        "herramienta": None,
    }
    assert llm.recibidos == []


def test_si_el_llm_no_encuentra_la_respuesta_dice_no_lo_se(
    client: TestClient, llm: LLMGrabador
) -> None:
    llm.respuesta = MARCA_NO_LO_SE

    respuesta = _preguntar(client, "¿Cuándo se poda el olivo?", "intereses", "agricultura")

    assert respuesta.json()["sabe"] is False
    assert respuesta.json()["citas"] == []


def test_sin_coleccion_busca_en_todo_el_espacio(client: TestClient, llm: LLMGrabador) -> None:
    llm.respuesta = "Se cosecha a mano [1]."

    respuesta = _preguntar(client, "¿Cómo es la cosecha de pitahaya?", "intereses")

    assert respuesta.json()["citas"][0]["documento"] == "pitahaya.txt"


def test_la_coleccion_acota_la_busqueda(client: TestClient) -> None:
    respuesta = _preguntar(client, "¿Cómo es la cosecha de pitahaya?", "intereses", "agricultura")

    assert all(cita["documento"] != "pitahaya.txt" for cita in respuesta.json()["citas"])


def test_un_espacio_no_ve_los_documentos_de_otro(client: TestClient) -> None:
    respuesta = _preguntar(client, "¿Fertilizacion con potasio?", "intereses")

    documentos = {cita["documento"] for cita in respuesta.json()["citas"]}
    assert "potasio.txt" not in documentos


def test_no_mezcla_vectores_de_otro_modelo(client: TestClient) -> None:
    from app.providers.embeddings import obtener_proveedor_embeddings
    from main import app

    app.dependency_overrides[obtener_proveedor_embeddings] = lambda: proveedor_doble(
        modelo_id="otro:modelo"
    )

    respuesta = _preguntar(client, "¿Cuál es el Kc del olivo?", "intereses", "agricultura")

    # Nunca devuelve trozos del otro modelo: avisa que hay que re-embeber (B2) en vez de mezclar.
    assert respuesta.status_code == 409
    assert "citas" not in respuesta.json()


def test_espacio_o_coleccion_inexistente_es_404(client: TestClient) -> None:
    assert _preguntar(client, "¿Kc?", "no-existe").status_code == 404
    assert _preguntar(client, "¿Kc?", "intereses", "no-existe").status_code == 404


def test_llm_caido_responde_502(client: TestClient, llm: LLMGrabador) -> None:
    llm.falla = True

    respuesta = _preguntar(client, "¿Cuál es el Kc del olivo?", "intereses", "agricultura")

    assert respuesta.status_code == 502


@pytest.mark.parametrize("vacia", ["", "   \n "], ids=["vacia", "solo-espacios"])
def test_respuesta_vacia_del_llm_es_falla_del_proveedor(
    client: TestClient, llm: LLMGrabador, vacia: str
) -> None:
    llm.respuesta = vacia

    respuesta = _preguntar(client, "¿Cuál es el Kc del olivo?", "intereses", "agricultura")

    assert respuesta.status_code == 502
    assert "vacía" in respuesta.json()["error"]


def test_el_prompt_indica_el_rango_cuando_el_trozo_cruza_paginas() -> None:
    from app.services.pregunta import Cita, _mensajes

    cita = Cita(1, "tabla.pdf", 4, 5, OrigenTrozo.TEXTO, fragmento="Kc 0,65", distancia=0.2)

    prompt = _mensajes("¿Kc?", [cita])[-1].text

    assert "[1] tabla.pdf, páginas 4-5" in prompt


def test_la_cita_y_el_prompt_dicen_cuando_el_fragmento_lo_genero_un_modelo(
    client: TestClient, llm: LLMGrabador
) -> None:
    client.post(
        "/api/espacios/intereses/colecciones/agricultura/documentos",
        files={"archivo": ("figura.pdf", pdf_minimo([FIGURA]))},
    )
    llm.respuesta = "Muestra el potasio absorbido [1]."

    respuesta = _preguntar(client, "¿Potasio en la cosecha?", "intereses", "agricultura")

    cita = respuesta.json()["citas"][0]
    assert (cita["documento"], cita["origen"]) == ("figura.pdf", "vision")
    assert "descripción automática de una imagen" in llm.recibidos[-1][-1].text
