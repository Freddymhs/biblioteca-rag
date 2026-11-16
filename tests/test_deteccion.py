import pytest

from app.common.errors import AppError
from app.config.constantes import MAX_BYTES_SUBIDA, TipoDocumento
from app.services.deteccion import detectar
from tests.pdf_minimo import pdf_minimo

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"


def test_pdf_se_detecta_por_firma_aunque_no_tenga_extension() -> None:
    assert detectar(pdf_minimo(["Hola"])).tipo == TipoDocumento.PDF


def test_pdf_con_basura_antes_de_la_firma() -> None:
    assert detectar(b"\n\r basura " + pdf_minimo(["Hola"])).tipo == TipoDocumento.PDF


def test_texto_utf8_con_tildes() -> None:
    assert detectar("Manejo del cultivo de maracuyá\n".encode()).tipo == TipoDocumento.TEXTO


@pytest.mark.parametrize(
    ("contenido", "motivo"),
    [
        (b"", "vacío"),
        (b"   \n\t ", "vacío"),
        (FIRMA_PNG + b"\x00\x00\x00\rIHDR", "no soportado"),  # imagen con nombre .pdf
        (b"PK\x03\x04" + bytes(range(256)), "no soportado"),  # zip/docx
        ("texto en latin-1: maracuyá".encode("latin-1"), "no soportado"),
    ],
    ids=["vacio", "solo-espacios", "png", "zip", "latin1"],
)
def test_rechaza_lo_que_no_es_documento(contenido: bytes, motivo: str) -> None:
    with pytest.raises(AppError) as error:
        detectar(contenido)

    assert error.value.status_code == 422
    assert motivo in error.value.message


def test_rechaza_archivo_demasiado_grande() -> None:
    with pytest.raises(AppError) as error:
        detectar(b"a" * (MAX_BYTES_SUBIDA + 1))

    assert error.value.status_code == 413


def test_mismo_contenido_mismo_hash_y_distinto_contenido_distinto_hash() -> None:
    primero = detectar(b"mismo texto")
    repetido = detectar(b"mismo texto")
    otro = detectar(b"otro texto")

    assert primero.hash_contenido == repetido.hash_contenido
    assert primero.hash_contenido != otro.hash_contenido
    assert len(primero.hash_contenido) == 64
