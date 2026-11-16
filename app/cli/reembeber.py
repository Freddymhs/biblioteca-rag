"""Re-embed de colecciones con el proveedor activo de `.env` (tarea 2.4).

    uv run python -m app.cli.reembeber --espacio laboral --coleccion agricultura
    uv run python -m app.cli.reembeber --espacio laboral               # todas las del espacio
    uv run python -m app.cli.reembeber --espacio laboral --retrocear   # además, re-trocea

Sin `--retrocear` solo re-vectoriza los documentos cuyo modelo no es el activo. Con `--retrocear`
vuelve a trocear desde el DoclingDocument guardado (los documentos sin él se saltan y se cuentan).
"""

import argparse
import sys

from app.common.logger import logger
from app.config.database import SessionLocal
from app.providers.embeddings import obtener_proveedor_embeddings
from app.services import catalogo
from app.services.reembebido import reembeber_coleccion


def main(argv: list[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    proveedor = obtener_proveedor_embeddings()
    with SessionLocal() as db:
        colecciones = (
            [argumentos.coleccion]
            if argumentos.coleccion
            else [c.slug for c in catalogo.listar_colecciones(db, argumentos.espacio)]
        )
        for coleccion in colecciones:
            resumen = reembeber_coleccion(
                db, argumentos.espacio, coleccion, proveedor, retrocear=argumentos.retrocear
            )
            logger.info(
                f"{argumentos.espacio}/{coleccion} → {proveedor.modelo_id}: "
                f"documentos {resumen.documentos} · trozos {resumen.trozos} · "
                f"saltados {resumen.saltados} · sin estructura {resumen.sin_estructura}"
            )
    logger.info(f"Colecciones procesadas: {len(colecciones)}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-embebe colecciones con el proveedor activo.")
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", help="sin ella, todas las colecciones del espacio")
    parser.add_argument("--retrocear", action="store_true", help="vuelve a trocear (Docling)")
    return parser


if __name__ == "__main__":
    sys.exit(main())
