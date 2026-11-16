import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.models import Documento, Trozo
from app.services import catalogo
from app.services.ingesta import ingestar
from tests.dobles import MODELO_DOBLE, EmbeddingsCaidos, proveedor_doble
from tests.pdf_minimo import pdf_minimo

URL_DOCUMENTOS = "/api/espacios/laboral/colecciones/agricultura/documentos"
PDF_OLIVO = pdf_minimo(["Riego del olivo\nEl Kc del olivo es 0.65.", "", "Poda del olivo"])


@pytest.fixture(autouse=True)
def coleccion_agricultura(db: Session) -> None:
    catalogo.crear_espacio(db, "laboral", "Laboral")
    catalogo.crear_coleccion(db, "laboral", "agricultura", "Agricultura")


def _subir(client: TestClient, nombre: str, contenido: bytes):
    return client.post(URL_DOCUMENTOS, files={"archivo": (nombre, contenido)})


def _contar(db: Session, modelo: type[Documento] | type[Trozo]) -> int:
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def test_subir_pdf_guarda_documento_y_trozos_con_pagina(client: TestClient, db: Session) -> None:
    respuesta = _subir(client, "olivo.pdf", PDF_OLIVO)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 201
    assert (cuerpo["tipo"], cuerpo["paginas"], cuerpo["paginas_sin_texto"]) == ("pdf", 3, [2])
    trozos = db.scalars(select(Trozo).order_by(Trozo.orden)).all()
    assert cuerpo["trozos"] == len(trozos) > 0
    assert {(t.pagina_inicio, t.pagina_fin) for t in trozos} == {(1, 1), (3, 3)}
    assert {t.embedding_model for t in trozos} == {MODELO_DOBLE}


def test_pdf_sin_extension_se_acepta_por_contenido(client: TestClient) -> None:
    respuesta = _subir(client, "Boletín INIA N° 259", PDF_OLIVO)

    assert respuesta.status_code == 201
    assert respuesta.json()["nombre_archivo"] == "Boletín INIA N° 259"


def test_texto_plano(client: TestClient) -> None:
    respuesta = _subir(client, "maracuya.txt", "El riego del maracuyá es diario.".encode())

    assert respuesta.status_code == 201
    assert (respuesta.json()["tipo"], respuesta.json()["paginas"]) == ("txt", None)


def test_mismo_archivo_dos_veces_no_duplica_trozos(client: TestClient, db: Session) -> None:
    primera = _subir(client, "olivo.pdf", PDF_OLIVO)
    trozos_tras_primera = _contar(db, Trozo)

    segunda = _subir(client, "otro-nombre.pdf", PDF_OLIVO)

    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert "olivo.pdf" in segunda.json()["error"]
    assert (_contar(db, Documento), _contar(db, Trozo)) == (1, trozos_tras_primera)


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("vacio.pdf", b""),
        ("imagen.pdf", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"),
        ("roto.pdf", b"%PDF-1.4\nno es un pdf"),
        ("escaneado.pdf", pdf_minimo(["", ""])),
    ],
    ids=["vacio", "tipo-falso", "pdf-corrupto", "sin-texto"],
)
def test_archivos_que_no_se_ingieren_responden_422(
    client: TestClient, db: Session, nombre: str, contenido: bytes
) -> None:
    respuesta = _subir(client, nombre, contenido)

    assert respuesta.status_code == 422
    assert _contar(db, Documento) == 0


def test_coleccion_inexistente_responde_404(client: TestClient) -> None:
    respuesta = client.post(
        "/api/espacios/laboral/colecciones/no-existe/documentos",
        files={"archivo": ("a.txt", b"hola")},
    )

    assert respuesta.status_code == 404


def test_proveedor_caido_responde_502_y_no_guarda_nada(client: TestClient, db: Session) -> None:
    from app.providers.embeddings import obtener_proveedor_embeddings
    from main import app

    app.dependency_overrides[obtener_proveedor_embeddings] = lambda: proveedor_doble(
        EmbeddingsCaidos()
    )

    respuesta = _subir(client, "olivo.pdf", PDF_OLIVO)

    assert respuesta.status_code == 502
    assert _contar(db, Documento) == 0


def test_documento_y_trozos_van_en_la_misma_transaccion(db: Session) -> None:
    """Si falla un trozo al escribir, el documento tampoco queda."""
    agricultura = catalogo.obtener_coleccion(db, "laboral", "agricultura")
    modelo_demasiado_largo = "x" * 300  # la columna embedding_model admite 200

    with pytest.raises(DataError):
        ingestar(
            db,
            agricultura,
            "olivo.pdf",
            PDF_OLIVO,
            proveedor_doble(modelo_id=modelo_demasiado_largo),
        )
    db.rollback()

    assert (_contar(db, Documento), _contar(db, Trozo)) == (0, 0)


def test_listado_de_documentos_con_conteo_de_trozos(client: TestClient) -> None:
    subido = _subir(client, "olivo.pdf", PDF_OLIVO).json()

    listado = client.get(URL_DOCUMENTOS).json()

    assert [(d["nombre_archivo"], d["trozos"]) for d in listado] == [
        ("olivo.pdf", subido["trozos"])
    ]


def test_nombre_de_archivo_demasiado_largo_responde_422(client: TestClient, db: Session) -> None:
    from app.config.constantes import MAX_LARGO_NOMBRE_ARCHIVO

    nombre = "a" * (MAX_LARGO_NOMBRE_ARCHIVO - len(".pdf") + 1) + ".pdf"

    respuesta = _subir(client, nombre, PDF_OLIVO)

    assert respuesta.status_code == 422
    assert _contar(db, Documento) == 0


@pytest.mark.parametrize("nombre", ["olivo\x00.pdf", "olivo\n.pdf"], ids=["nul", "salto"])
def test_nombre_con_caracteres_de_control_se_rechaza(db: Session, nombre: str) -> None:
    from app.common.errors import AppError

    agricultura = catalogo.obtener_coleccion(db, "laboral", "agricultura")

    with pytest.raises(AppError) as error:
        ingestar(db, agricultura, nombre, PDF_OLIVO, proveedor_doble())

    assert error.value.status_code == 422


def test_sin_nombre_usa_el_nombre_por_defecto(db: Session) -> None:
    from app.config.constantes import NOMBRE_ARCHIVO_POR_DEFECTO

    agricultura = catalogo.obtener_coleccion(db, "laboral", "agricultura")

    resultado = ingestar(db, agricultura, "   ", PDF_OLIVO, proveedor_doble())

    assert resultado.documento.nombre_archivo == NOMBRE_ARCHIVO_POR_DEFECTO


def test_no_queda_transaccion_abierta_mientras_se_extrae_y_embebe(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Docling y la red pueden tardar minutos: la conexión no debe quedar «idle in transaction»."""
    from app.services import ingesta as modulo_ingesta
    from tests.dobles import EmbeddingsPorPalabras

    estados: list[tuple[str, bool]] = []
    extraer_real = modulo_ingesta.extraer

    def extraer_espia(*argumentos, **opciones):
        estados.append(("extraer", db.in_transaction()))
        return extraer_real(*argumentos, **opciones)

    class EmbeddingsEspia(EmbeddingsPorPalabras):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            estados.append(("embeber", db.in_transaction()))
            return super().embed_documents(texts)

    monkeypatch.setattr(modulo_ingesta, "extraer", extraer_espia)
    agricultura = catalogo.obtener_coleccion(db, "laboral", "agricultura")

    ingestar(db, agricultura, "olivo.pdf", PDF_OLIVO, proveedor_doble(EmbeddingsEspia()))

    assert estados == [("extraer", False), ("embeber", False)]
