"""Sincroniza una colección con un conector, en primer plano (re-sync manual o desde cron).

    uv run python -m app.cli.sincronizar --espacio personal --coleccion sobre-mi --conector resume

Programado: una línea de cron del host que corra este comando. Por la API, el mismo trabajo va
en segundo plano: `POST /api/espacios/{e}/colecciones/{c}/sincronizaciones`.
"""

import argparse
import sys

from app.common.logger import logger
from app.conectores import crear_conector
from app.config.constantes import SALIDA_CON_ERRORES
from app.config.database import SessionLocal
from app.config.settings import settings
from app.providers.embeddings import obtener_proveedor_embeddings
from app.services.sincronizacion import sincronizar_coleccion


def main(argv: list[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    conector = crear_conector(argumentos.conector, settings)
    with SessionLocal() as db:
        resumen = sincronizar_coleccion(
            db,
            argumentos.espacio,
            argumentos.coleccion,
            conector,
            obtener_proveedor_embeddings(),
            permitir_vaciar=argumentos.permitir_vaciar,
        )
    logger.info(f"{argumentos.conector} → {argumentos.espacio}/{argumentos.coleccion}: {resumen}")
    return SALIDA_CON_ERRORES if resumen.errores else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sincroniza una colección con un conector.")
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", required=True)
    parser.add_argument("--conector", required=True, help="ej. resume")
    parser.add_argument(
        "--permitir-vaciar",
        action="store_true",
        help="si la fuente no trae registros, borrar la colección (si no, es error)",
    )
    return parser


if __name__ == "__main__":
    sys.exit(main())
