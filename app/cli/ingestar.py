"""Ingesta de una carpeta completa, un archivo por transacción.

    uv run python -m app.cli.ingestar <carpeta> --espacio laboral --coleccion agricultura \
        --catalogo <carpeta>/catalogo.json \
        --excluir catalogo.json --excluir prompt.txt --excluir LIBROS_POR_REBUSCAR.md

`--catalogo` (opcional, 6.1): JSON con título, fuente y año por nombre de archivo (ver
`app/services/metadatos.py`); la cita muestra ese título.

El espacio y la colección deben existir (se crean por la API). Un archivo que falla no detiene
al resto. Sale con código 1 si hubo errores inesperados (no cuenta duplicados ni rechazos).
"""

import argparse
import fnmatch
import sys
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.common.logger import logger
from app.config.constantes import SALIDA_CON_ERRORES
from app.config.database import SessionLocal
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.providers.vision import obtener_vision
from app.schemas.documento import MetadatosDocumento
from app.services.ingesta_por_lotes import Resultado, ingestar_en_lote
from app.services.metadatos import leer_catalogo


def main(argv: list[str] | None = None) -> int:
    return main_con(
        argv,
        abrir_sesion=SessionLocal,
        obtener_proveedor=obtener_proveedor_embeddings,
        vision=obtener_vision(),
    )


def main_con(
    argv: list[str] | None,
    *,
    abrir_sesion: Callable[[], AbstractContextManager[Session]],
    obtener_proveedor: Callable[[], ProveedorDeEmbeddings],
    vision: BaseChatModel | None,
) -> int:
    """`main` con sus piezas inyectadas (base, embeddings, visión): así se prueba entera."""
    argumentos = _parser().parse_args(argv)
    archivos = archivos_a_ingerir(argumentos.carpeta, argumentos.excluir)
    catalogo = leer_catalogo(argumentos.catalogo) if argumentos.catalogo else {}
    _avisar_cobertura(archivos, catalogo)
    totales = ingestar_carpeta(
        archivos,
        argumentos.espacio,
        argumentos.coleccion,
        abrir_sesion,
        obtener_proveedor,
        vision,
        catalogo,
    )
    resumen = " · ".join(f"{resultado.value}: {totales[resultado]}" for resultado in Resultado)
    logger.info(f"Archivos: {len(archivos)} · {resumen} · trozos: {totales['trozos']}")
    return SALIDA_CON_ERRORES if totales[Resultado.ERROR] else 0


def archivos_a_ingerir(carpeta: Path, excluir: list[str]) -> list[Path]:
    return sorted(
        ruta
        for ruta in carpeta.rglob("*")
        if ruta.is_file() and not any(fnmatch.fnmatch(ruta.name, patron) for patron in excluir)
    )


def ingestar_carpeta(
    archivos: list[Path],
    espacio: str,
    coleccion: str,
    abrir_sesion: Callable[[], AbstractContextManager[Session]],
    obtener_proveedor: Callable[[], ProveedorDeEmbeddings],
    vision: BaseChatModel | None,
    catalogo: dict[str, MetadatosDocumento] | None = None,
) -> Counter[str]:
    totales: Counter[str] = Counter()
    metadatos_de = catalogo or {}
    proveedor = obtener_proveedor()
    for numero, ruta in enumerate(archivos, start=1):
        prefijo = f"[{numero}/{len(archivos)}] {ruta.name}"
        with abrir_sesion() as db:
            resultado, trozos = _ingestar_uno(
                db,
                ruta,
                espacio,
                coleccion,
                proveedor,
                vision,
                prefijo,
                metadatos_de.get(ruta.name),
            )
        totales[resultado] += 1
        totales["trozos"] += trozos
    return totales


def _ingestar_uno(
    db: Session,
    ruta: Path,
    espacio: str,
    coleccion: str,
    proveedor: ProveedorDeEmbeddings,
    vision: BaseChatModel | None,
    prefijo: str,
    metadatos: MetadatosDocumento | None,
) -> tuple[Resultado, int]:
    archivo = ingestar_en_lote(
        db,
        espacio,
        coleccion,
        ruta.name,
        ruta.read_bytes(),
        proveedor,
        vision,
        prefijo,
        metadatos=metadatos,
    )
    return archivo.resultado, archivo.trozos


def _avisar_cobertura(archivos: list[Path], catalogo: dict[str, MetadatosDocumento]) -> None:
    if not catalogo:
        return
    nombres = {ruta.name for ruta in archivos}
    sin_archivo = sorted(set(catalogo) - nombres)
    logger.info(
        f"Catálogo: {len(nombres & set(catalogo))} de {len(archivos)} archivos con metadatos"
    )
    if sin_archivo:
        logger.warning(f"Entradas del catálogo sin archivo en la carpeta: {sin_archivo}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingesta una carpeta en una colección.")
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", required=True)
    parser.add_argument(
        "--catalogo",
        type=Path,
        help="JSON con título, fuente y año por nombre de archivo (opcional)",
    )
    parser.add_argument(
        "--excluir",
        action="append",
        default=[],
        help="patrón de nombre a saltar (repetible), ej. catalogo.json o '*.md'",
    )
    return parser


if __name__ == "__main__":
    sys.exit(main())
