from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.cli.ingestar import Resultado, archivos_a_ingerir, ingestar_carpeta
from app.common.errors import conflict, unprocessable
from app.services import catalogo
from app.services.ingesta import DocumentoDuplicado
from tests.dobles import EmbeddingsCaidos, proveedor_doble
from tests.pdf_minimo import pdf_minimo


@pytest.fixture
def carpeta(tmp_path: Path) -> Path:
    (tmp_path / "olivo.pdf").write_bytes(pdf_minimo(["Riego del olivo"]))
    (tmp_path / "Boletín sin extensión").write_bytes(pdf_minimo(["Poda del olivo"]))
    (tmp_path / "copia-del-olivo.pdf").write_bytes(pdf_minimo(["Riego del olivo"]))
    (tmp_path / "vacio.pdf").write_bytes(b"")
    (tmp_path / "catalogo.json").write_text('{"control": true}')
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "maracuya.txt").write_text("Riego del maracuyá.")
    return tmp_path


@pytest.fixture
def abrir_sesion(db: Session):
    catalogo.crear_espacio(db, "intereses", "Intereses")
    catalogo.crear_coleccion(db, "intereses", "agricultura", "Agricultura")

    @contextmanager
    def _sesion() -> Generator[Session, None, None]:
        yield db  # la del test: todo se revierte al final

    return _sesion


def test_excluye_por_patron_y_recorre_subcarpetas(carpeta: Path) -> None:
    nombres = {ruta.name for ruta in archivos_a_ingerir(carpeta, ["catalogo.json"])}

    assert nombres == {
        "olivo.pdf",
        "Boletín sin extensión",
        "copia-del-olivo.pdf",
        "vacio.pdf",
        "maracuya.txt",
    }


def test_cuenta_cada_resultado_sin_detenerse(carpeta: Path, abrir_sesion) -> None:
    archivos = archivos_a_ingerir(carpeta, ["catalogo.json"])

    totales = ingestar_carpeta(
        archivos, "intereses", "agricultura", abrir_sesion, proveedor_doble, None
    )

    assert totales[Resultado.INGERIDO] == 3  # olivo, boletín sin extensión, maracuyá
    assert totales[Resultado.DUPLICADO] == 1  # la copia del olivo
    assert totales[Resultado.RECHAZADO] == 1  # el vacío
    assert totales[Resultado.ERROR] == 0
    assert sum(totales[r] for r in Resultado) == len(archivos)


def test_proveedor_caido_cuenta_como_error(carpeta: Path, abrir_sesion) -> None:
    archivos = archivos_a_ingerir(carpeta, ["catalogo.json", "vacio.pdf"])

    totales = ingestar_carpeta(
        archivos,
        "intereses",
        "agricultura",
        abrir_sesion,
        lambda: proveedor_doble(EmbeddingsCaidos()),
        None,
    )

    assert totales[Resultado.ERROR] == len(archivos)


@pytest.mark.parametrize(
    ("error", "esperado"),
    [
        (DocumentoDuplicado("ya está"), Resultado.DUPLICADO),
        (conflict("otro conflicto que no es un documento repetido"), Resultado.RECHAZADO),
        (unprocessable("vacío"), Resultado.RECHAZADO),
    ],
    ids=["duplicado", "otro-409", "422"],
)
def test_clasifica_por_tipo_de_error_y_no_por_codigo(
    tmp_path: Path, abrir_sesion, monkeypatch: pytest.MonkeyPatch, error, esperado
) -> None:
    from app.services import ingesta_por_lotes

    def ingestar_que_falla(*_argumentos, **_opciones):
        raise error

    monkeypatch.setattr(ingesta_por_lotes, "ingestar", ingestar_que_falla)
    archivo = tmp_path / "a.txt"
    archivo.write_text("hola")

    totales = ingestar_carpeta(
        [archivo], "intereses", "agricultura", abrir_sesion, proveedor_doble, None
    )

    assert totales[esperado] == 1
