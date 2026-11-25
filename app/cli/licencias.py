"""Marca las licencias de una colección según una tabla con veredicto (FASE_6, 6.7).

    uv run python -m app.cli.licencias --espacio intereses --coleccion agricultura \
        --tabla docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md            # solo muestra
    uv run python -m app.cli.licencias ... --aplicar                         # escribe

Se corre DESPUÉS de la ingesta. Sin `--aplicar` no escribe nada: muestra cuántos se publicarían.
Un documento que la tabla no nombra queda como estaba (sin verificar, si nadie lo tocó).

K3: sale con SALIDA_CON_ERRORES si ninguna fila calza con la colección (¿otra colección, o la
ingesta no corrió?) o si con `--aplicar` quedan filas de la tabla sin documento.
"""

import argparse
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from sqlalchemy.orm import Session

from app.common.logger import logger
from app.config.constantes import SALIDA_CON_ERRORES
from app.config.database import SessionLocal
from app.services import catalogo
from app.services.licencias import aplicar_licencias, leer_tabla_licencias


def main(argv: list[str] | None = None) -> int:
    return main_con(argv, abrir_sesion=SessionLocal)


def main_con(
    argv: list[str] | None, *, abrir_sesion: Callable[[], AbstractContextManager[Session]]
) -> int:
    argumentos = _parser().parse_args(argv)
    filas = leer_tabla_licencias(argumentos.tabla)
    with abrir_sesion() as db:
        destino = catalogo.obtener_coleccion(db, argumentos.espacio, argumentos.coleccion)
        resumen = aplicar_licencias(db, destino, filas, aplicar=argumentos.aplicar)
    modo = "aplicado" if argumentos.aplicar else "simulado (sin --aplicar no se escribe nada)"
    logger.info(
        f"Licencias {modo}: filas {resumen.filas} · verificadas {resumen.verificadas} · "
        f"sin publicar {resumen.sin_publicar}"
    )
    if resumen.sin_documento:
        logger.warning(f"En la tabla y no en la colección: {resumen.sin_documento}")
    if resumen.sin_fila:
        logger.warning(
            f"En la colección y no en la tabla (quedan como estaban): {resumen.sin_fila}"
        )
    ninguna_calza = resumen.calzadas == 0
    if ninguna_calza:
        logger.error("Ninguna fila de la tabla nombra un documento de la colección")
    sin_documento_al_aplicar = argumentos.aplicar and bool(resumen.sin_documento)
    if sin_documento_al_aplicar:
        logger.error(f"Aplicado, pero {len(resumen.sin_documento)} filas no tienen documento")
    return SALIDA_CON_ERRORES if ninguna_calza or sin_documento_al_aplicar else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Marca licencias según una tabla con veredicto.")
    parser.add_argument("--tabla", type=Path, required=True)
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", required=True)
    parser.add_argument("--aplicar", action="store_true", help="sin esto, solo muestra el resumen")
    return parser


if __name__ == "__main__":
    sys.exit(main())
