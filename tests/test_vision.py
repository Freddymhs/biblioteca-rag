from app.config.constantes import OrigenTrozo
from app.services.vision import indexar_paginas_sin_texto
from tests.dobles import LLMGrabador
from tests.pdf_minimo import FIGURA, pdf_minimo

PDF = pdf_minimo(["Texto de la pagina uno", FIGURA, ""])
DESCRIPCION = "A bar chart of potassium uptake by month."


def _imagenes_enviadas(vision: LLMGrabador) -> list[str]:
    return [
        bloque["image_url"]["url"]
        for conversacion in vision.recibidos
        for mensaje in conversacion
        for bloque in mensaje.content
        if isinstance(bloque, dict) and bloque.get("type") == "image_url"
    ]


def test_pagina_con_figura_se_describe_y_queda_como_trozo_de_vision() -> None:
    vision = LLMGrabador(respuesta=DESCRIPCION)

    resultado = indexar_paginas_sin_texto(PDF, [2], vision, "doc.pdf")

    assert resultado.descritas == [2]
    assert [(t.texto, t.pagina_inicio, t.pagina_fin, t.origen) for t in resultado.trozos] == [
        (DESCRIPCION, 2, 2, OrigenTrozo.VISION)
    ]
    imagenes = _imagenes_enviadas(vision)
    assert len(imagenes) == 1
    assert imagenes[0].startswith("data:image/png;base64,")


def test_pagina_en_blanco_no_se_manda_al_modelo() -> None:
    """Medido: con una página en blanco, moondream inventa «franjas grises»."""
    vision = LLMGrabador(respuesta=DESCRIPCION)

    resultado = indexar_paginas_sin_texto(PDF, [3], vision, "doc.pdf")

    assert resultado.en_blanco == [3]
    assert resultado.trozos == []
    assert vision.recibidos == []


def test_respuesta_vacia_deja_la_pagina_sin_indexar() -> None:
    resultado = indexar_paginas_sin_texto(PDF, [2], LLMGrabador(respuesta="  "), "doc.pdf")

    assert (resultado.trozos, resultado.sin_indexar) == ([], [2])


def test_proveedor_caido_deja_la_pagina_sin_indexar_sin_romper_la_ingesta() -> None:
    resultado = indexar_paginas_sin_texto(PDF, [2], LLMGrabador(falla=True), "doc.pdf")

    assert (resultado.trozos, resultado.sin_indexar) == ([], [2])


def test_sin_proveedor_de_vision_detecta_blancos_y_no_indexa_el_resto() -> None:
    resultado = indexar_paginas_sin_texto(PDF, [2, 3], None, "doc.pdf")

    assert (resultado.en_blanco, resultado.sin_indexar, resultado.trozos) == ([3], [2], [])


def test_sin_paginas_pendientes_no_abre_el_archivo() -> None:
    """El texto plano no es un PDF: pdfium fallaría al abrirlo."""
    resultado = indexar_paginas_sin_texto(b"texto plano", [], LLMGrabador(), "nota.txt")

    assert resultado.trozos == []
