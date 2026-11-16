"""Ingesta de una carpeta completa, un archivo por transacción.

    uv run python -m app.cli.ingestar <carpeta> --espacio laboral --coleccion agricultura \
        --excluir catalogo.json --excluir prompt.txt --excluir LIBROS_POR_REBUSCAR.md

El espacio y la colección deben existir (se crean por la API). Un archivo que falla no detiene
al resto. Sale con código 1 si hubo errores inesperados (no cuenta duplicados ni rechazos).
"""

import argparse
import fnmatch
import sys
from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from sqlalchemy.orm import Session

from app.common.errors import AppError, ErrorProveedor
from app.common.logger import logger
from app.config.database import SessionLocal
from app.providers.embeddings import ProveedorDeEmbeddings, obtener_proveedor_embeddings
from app.services import catalogo
from app.services.ingesta import DocumentoDuplicado, ingestar

SALIDA_CON_ERRORES = 1


class Resultado(StrEnum):
    INGERIDO = "ingeridos"
    DUPLICADO = "duplicados"
    RECHAZADO = "rechazados"
    ERROR = "errores"


def main(argv: list[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    archivos = archivos_a_ingerir(argumentos.carpeta, argumentos.excluir)
    totales = ingestar_carpeta(
        archivos,
        argumentos.espacio,
        argumentos.coleccion,
        SessionLocal,
        obtener_proveedor_embeddings,
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
    abrir_sesion: Callable[[], Session],
    obtener_proveedor: Callable[[], ProveedorDeEmbeddings],
) -> Counter[str]:
    totales: Counter[str] = Counter()
    proveedor = obtener_proveedor()
    for numero, ruta in enumerate(archivos, start=1):
        prefijo = f"[{numero}/{len(archivos)}] {ruta.name}"
        with abrir_sesion() as db:
            resultado, trozos = _ingestar_uno(db, ruta, espacio, coleccion, proveedor, prefijo)
        totales[resultado] += 1
        totales["trozos"] += trozos
    return totales


def _ingestar_uno(
    db: Session,
    ruta: Path,
    espacio: str,
    coleccion: str,
    proveedor: ProveedorDeEmbeddings,
    prefijo: str,
) -> tuple[Resultado, int]:
    try:
        destino = catalogo.obtener_coleccion(db, espacio, coleccion)
        resultado = ingestar(db, destino, ruta.name, ruta.read_bytes(), proveedor)
    except DocumentoDuplicado as error:
        logger.warning(f"{prefijo}: {Resultado.DUPLICADO.value} — {error.message}")
        return Resultado.DUPLICADO, 0
    except AppError as error:
        logger.warning(f"{prefijo}: {Resultado.RECHAZADO.value} — {error.message}")
        return Resultado.RECHAZADO, 0
    except ErrorProveedor as error:
        logger.error(f"{prefijo}: proveedor — {error}")
        return Resultado.ERROR, 0
    except Exception:
        # Inesperado: se registra con traza y se sigue con el siguiente archivo.
        logger.exception(f"{prefijo}: error inesperado")
        db.rollback()
        return Resultado.ERROR, 0
    logger.info(f"{prefijo}: {resultado.trozos} trozos")
    return Resultado.INGERIDO, resultado.trozos


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingesta una carpeta en una colección.")
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", required=True)
    parser.add_argument(
        "--excluir",
        action="append",
        default=[],
        help="patrón de nombre a saltar (repetible), ej. catalogo.json o '*.md'",
    )
    return parser


if __name__ == "__main__":
    sys.exit(main())
