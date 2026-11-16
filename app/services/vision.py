"""Páginas sin capa de texto: en blanco se descartan; con contenido las describe un modelo.

Determinista primero: Docling copia el texto que el PDF ya tiene; el modelo solo mira lo que no
tiene texto. Una página que el modelo no pudo describir queda sin indexar y se registra: la
ingesta del documento sigue.
"""

from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from langchain_core.language_models import BaseChatModel
from PIL import Image

from app.common.logger import logger
from app.config.constantes import (
    ESCALA_DETECCION_BLANCO,
    ESCALA_RENDER_VISION,
    GRIS_MAXIMO_TINTA,
    PROPORCION_MINIMA_TINTA,
    OrigenTrozo,
)
from app.providers.llm import ErrorLLM
from app.providers.vision import describir_imagen
from app.services.extraccion import TrozoExtraido


@dataclass(frozen=True)
class ResultadoVision:
    trozos: list[TrozoExtraido]
    descritas: list[int]
    en_blanco: list[int]
    sin_indexar: list[int]


def indexar_paginas_sin_texto(
    contenido_pdf: bytes,
    paginas: list[int],
    vision: BaseChatModel | None,
    nombre_archivo: str,
) -> ResultadoVision:
    if not paginas:  # también cubre el texto plano, que no es un PDF y no se abre con pdfium
        return ResultadoVision(trozos=[], descritas=[], en_blanco=[], sin_indexar=[])
    trozos: list[TrozoExtraido] = []
    descritas: list[int] = []
    en_blanco: list[int] = []
    sin_indexar: list[int] = []
    documento = pdfium.PdfDocument(contenido_pdf)
    try:
        for numero in paginas:
            pagina = documento[numero - 1]  # Docling numera desde 1, pdfium desde 0
            if _en_blanco(pagina):
                en_blanco.append(numero)
                continue
            descripcion = _describir(pagina, vision, nombre_archivo, numero)
            if descripcion is None:
                sin_indexar.append(numero)
                continue
            descritas.append(numero)
            trozos.append(
                TrozoExtraido(
                    texto=descripcion,
                    pagina_inicio=numero,
                    pagina_fin=numero,
                    origen=OrigenTrozo.VISION,
                )
            )
    finally:
        documento.close()
    if sin_indexar:
        logger.warning(
            f"{nombre_archivo}: páginas sin indexar (sin visión o sin respuesta): {sin_indexar}"
        )
    return ResultadoVision(trozos, descritas, en_blanco, sin_indexar)


# pypdfium2 no anota `scale`: su docstring dice float y pyright infiere int del default `1`.
def _render(pagina: pdfium.PdfPage, escala: float) -> Image.Image:
    return pagina.render(scale=escala).to_pil()  # type: ignore[arg-type]  # ver nota


def _en_blanco(pagina: pdfium.PdfPage) -> bool:
    gris = _render(pagina, ESCALA_DETECCION_BLANCO).convert("L")
    histograma = gris.histogram()
    con_tinta = sum(histograma[:GRIS_MAXIMO_TINTA])
    return con_tinta / sum(histograma) < PROPORCION_MINIMA_TINTA


def _describir(
    pagina: pdfium.PdfPage, vision: BaseChatModel | None, nombre_archivo: str, numero: int
) -> str | None:
    if vision is None:
        return None
    imagen = BytesIO()
    _render(pagina, ESCALA_RENDER_VISION).save(imagen, format="PNG")
    try:
        return describir_imagen(vision, imagen.getvalue())
    except ErrorLLM as error:
        logger.warning(f"{nombre_archivo}: página {numero} sin describir: {error}")
        return None
