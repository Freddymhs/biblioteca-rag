"""Texto + tablas con Docling y troceo con HybridChunker (respeta títulos y tablas).

Las páginas sin capa de texto se informan; las procesa `app/services/vision.py`.
"""

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import Any

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError, DocumentLoadError
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.picture.picture import PictureItem

from app.common.errors import unprocessable
from app.common.logger import logger
from app.config.constantes import (
    MAX_TOKENS_POR_TROZO,
    TOKENIZADOR_TROZOS,
    OrigenTrozo,
    TipoDocumento,
)

# Docling elige el parser por la extensión del nombre: se la damos según el tipo DETECTADO,
# no según el nombre original (que puede no tener extensión o mentir).
NOMBRE_INTERNO_POR_TIPO = {
    TipoDocumento.PDF: "documento.pdf",
    TipoDocumento.TEXTO: "documento.md",  # texto plano es Markdown válido
}
DELIMITADOR = "\n"  # el mismo que usa HybridChunker


@dataclass(frozen=True)
class TrozoExtraido:
    texto: str
    # Rango y no una sola página: un elemento (tabla, párrafo) puede venir partido entre dos.
    pagina_inicio: int | None
    pagina_fin: int | None
    origen: OrigenTrozo = OrigenTrozo.TEXTO


@dataclass(frozen=True)
class Extraccion:
    trozos: list[TrozoExtraido]
    paginas: int | None
    paginas_sin_texto: list[int]
    # El DoclingDocument serializado: permite volver a trocear sin volver a extraer (re-embed).
    estructura: dict[str, Any]


# El conversor y el chunker son únicos por proceso (`lru_cache`) y Docling no documenta que sean
# seguros entre hilos; la API extrae desde el threadpool de FastAPI. Se serializa: además, dos
# conversiones a la vez duplican la memoria de Docling.
_CANDADO_DOCLING = threading.Lock()


def extraer(contenido: bytes, tipo: TipoDocumento, nombre_archivo: str) -> Extraccion:
    with _CANDADO_DOCLING:
        documento = _convertir(contenido, tipo)
        trozos = _trocear(documento)
    paginas = len(documento.pages) if tipo == TipoDocumento.PDF else None
    sin_texto = _paginas_sin_texto(documento)
    if sin_texto:
        logger.warning(
            f"{nombre_archivo}: {len(sin_texto)} de {paginas} páginas "
            f"sin capa de texto: {sin_texto}"
        )
    return Extraccion(
        trozos=trozos,
        paginas=paginas,
        paginas_sin_texto=sin_texto,
        estructura=documento.export_to_dict(),
    )


def trocear_estructura(estructura: dict[str, Any]) -> list[TrozoExtraido]:
    """Trozos de texto desde un DoclingDocument guardado, con el troceador de hoy."""
    documento = DoclingDocument.model_validate(estructura)
    with _CANDADO_DOCLING:
        return _trocear(documento)


def _convertir(contenido: bytes, tipo: TipoDocumento) -> DoclingDocument:
    origen = DocumentStream(name=NOMBRE_INTERNO_POR_TIPO[tipo], stream=BytesIO(contenido))
    try:
        resultado = _conversor().convert(origen)
    except (ConversionError, DocumentLoadError) as error:
        # Solo los errores del ARCHIVO son 422. Un fallo al cargar modelos u otro error interno
        # se propaga como 500: no es culpa de quien sube.
        logger.warning(f"Docling no pudo convertir el archivo: {error!r}")
        raise unprocessable(
            "El archivo no se pudo leer: está dañado o no es lo que dice ser"
        ) from error
    return resultado.document


def _trocear(documento: DoclingDocument) -> list[TrozoExtraido]:
    """Une piezas vecinas solo si comparten página y títulos, hasta el máximo de tokens.

    El `merge_peers` de HybridChunker une piezas de páginas distintas, y la cita diría la
    página de la primera para un texto que está en otra. Por eso se desactiva y se une aquí.
    """
    piezas = _piezas(documento)
    tokenizador = _chunker().tokenizer
    trozos: list[TrozoExtraido] = []
    actual: _Pieza | None = None
    for pieza in piezas:
        if actual is None:
            actual = pieza
            continue
        unida = actual.unir(pieza)
        cabe = tokenizador.count_tokens(unida.texto_contextualizado()) <= MAX_TOKENS_POR_TROZO
        if actual.misma_ubicacion(pieza) and cabe:
            actual = unida
        else:
            trozos.append(actual.como_trozo())
            actual = pieza
    if actual is not None:
        trozos.append(actual.como_trozo())
    return trozos


@dataclass(frozen=True)
class _Pieza:
    pagina_inicio: int | None
    pagina_fin: int | None
    titulos: tuple[str, ...]
    cuerpo: str

    def misma_ubicacion(self, otra: "_Pieza") -> bool:
        mismas_paginas = (self.pagina_inicio, self.pagina_fin) == (
            otra.pagina_inicio,
            otra.pagina_fin,
        )
        return mismas_paginas and self.titulos == otra.titulos

    def unir(self, otra: "_Pieza") -> "_Pieza":
        cuerpo = f"{self.cuerpo}{DELIMITADOR}{otra.cuerpo}"
        return _Pieza(self.pagina_inicio, self.pagina_fin, self.titulos, cuerpo)

    def texto_contextualizado(self) -> str:
        """Mismo formato que `HybridChunker.contextualize`: títulos y luego el cuerpo."""
        return DELIMITADOR.join([*self.titulos, self.cuerpo])

    def como_trozo(self) -> TrozoExtraido:
        return TrozoExtraido(
            texto=self.texto_contextualizado(),
            pagina_inicio=self.pagina_inicio,
            pagina_fin=self.pagina_fin,
        )


def _piezas(documento: DoclingDocument) -> list[_Pieza]:
    piezas: list[_Pieza] = []
    for chunk in _chunker().chunk(dl_doc=documento):
        cuerpo = chunk.text.strip()
        if not cuerpo:
            continue
        meta = chunk.meta  # DocMeta: HybridChunker siempre la produce
        inicio, fin = rango_de_paginas(meta.doc_items)  # type: ignore[attr-defined]
        titulos = tuple(meta.headings or [])  # type: ignore[attr-defined]
        piezas.append(_Pieza(inicio, fin, titulos, cuerpo))
    return piezas


# `Any`: elementos de Docling (DocItem) o cualquier objeto con `prov[].page_no`.
def rango_de_paginas(items: Iterable[Any]) -> tuple[int | None, int | None]:
    paginas = [procedencia.page_no for item in items for procedencia in item.prov]
    if not paginas:
        return None, None
    return min(paginas), max(paginas)


def _paginas_sin_texto(documento: DoclingDocument) -> list[int]:
    """Una figura sola (`PictureItem`) no es texto: esa página la tiene que mirar la visión."""
    paginas_con_texto = {
        procedencia.page_no
        for item, _ in documento.iterate_items()
        if not isinstance(item, PictureItem)
        for procedencia in getattr(item, "prov", [])
    }
    return sorted(set(documento.pages) - paginas_con_texto)


@lru_cache(maxsize=1)
def _conversor() -> DocumentConverter:
    """Carga los modelos de layout y tablas una sola vez por proceso."""
    opciones = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.MD],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opciones)},
    )


@lru_cache(maxsize=1)
def _chunker() -> HybridChunker:
    tokenizador = HuggingFaceTokenizer.from_pretrained(
        model_name=TOKENIZADOR_TROZOS, max_tokens=MAX_TOKENS_POR_TROZO
    )
    return HybridChunker(tokenizer=tokenizador, merge_peers=False)


def precargar_modelos() -> None:
    """B6: baja (o carga de la caché) los mismos modelos que usa `extraer`, sin convertir nada.
    La imagen de Docker lo corre al construirse: la primera subida no espera la descarga."""
    _conversor().initialize_pipeline(InputFormat.PDF)
    _chunker()
