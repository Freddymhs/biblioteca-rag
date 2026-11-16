from types import SimpleNamespace

import pytest

from app.common.errors import AppError
from app.config.constantes import TipoDocumento
from app.services.extraccion import extraer, rango_de_paginas
from tests.pdf_minimo import pdf_minimo

PAGINA_RIEGO = (
    "Riego del olivo\nEl coeficiente de cultivo Kc del olivo en plena produccion es 0.65."
)
PAGINA_PODA = "Poda de formacion\nLa poda de formacion se realiza en los primeros tres anos."


def test_pdf_trozos_con_pagina_y_paginas_sin_texto() -> None:
    contenido = pdf_minimo([PAGINA_RIEGO, "", PAGINA_PODA])

    extraccion = extraer(contenido, TipoDocumento.PDF, "olivo.pdf")

    textos_por_pagina = {trozo.pagina_inicio: trozo.texto for trozo in extraccion.trozos}
    assert all(t.pagina_inicio == t.pagina_fin for t in extraccion.trozos)
    assert extraccion.paginas == 3
    assert extraccion.paginas_sin_texto == [2]
    assert "0.65" in textos_por_pagina[1]
    assert "primeros tres anos" in textos_por_pagina[3]
    assert 2 not in textos_por_pagina


def test_texto_plano_sin_paginas() -> None:
    contenido = "Manejo integrado del cultivo de maracuyá.\n\nSe riega cada tres días.".encode()

    extraccion = extraer(contenido, TipoDocumento.TEXTO, "maracuya.txt")

    assert extraccion.paginas is None
    assert extraccion.paginas_sin_texto == []
    rangos = [(trozo.pagina_inicio, trozo.pagina_fin) for trozo in extraccion.trozos]
    assert rangos == [(None, None)] * len(extraccion.trozos)
    assert "maracuyá" in " ".join(trozo.texto for trozo in extraccion.trozos)


def test_pdf_escaneado_no_produce_trozos() -> None:
    extraccion = extraer(pdf_minimo(["", ""]), TipoDocumento.PDF, "escaneado.pdf")

    assert extraccion.trozos == []
    assert extraccion.paginas_sin_texto == [1, 2]


def test_pdf_con_firma_pero_corrupto_se_rechaza() -> None:
    with pytest.raises(AppError) as error:
        extraer(b"%PDF-1.4\nesto no es un pdf de verdad", TipoDocumento.PDF, "falso.pdf")

    assert error.value.status_code == 422


def _item(*paginas: int) -> SimpleNamespace:
    return SimpleNamespace(prov=[SimpleNamespace(page_no=pagina) for pagina in paginas])


@pytest.mark.parametrize(
    ("items", "esperado"),
    [
        ([_item(3)], (3, 3)),
        ([_item(3), _item(4)], (3, 4)),  # dos elementos, uno en cada página
        ([_item(5, 6)], (5, 6)),  # un elemento (tabla, párrafo) partido entre páginas
        ([SimpleNamespace(prov=[])], (None, None)),  # texto plano: sin páginas
    ],
    ids=["una-pagina", "dos-elementos", "elemento-partido", "sin-paginas"],
)
def test_rango_de_paginas_de_un_trozo(items: list, esperado: tuple) -> None:
    assert rango_de_paginas(items) == esperado
