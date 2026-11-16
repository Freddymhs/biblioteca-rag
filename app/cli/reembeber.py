"""Re-embed de colecciones con el proveedor activo de `.env` (tarea 2.4).

    uv run python -m app.cli.reembeber --espacio laboral --coleccion agricultura
    uv run python -m app.cli.reembeber --espacio laboral               # todas las del espacio
    uv run python -m app.cli.reembeber --espacio laboral --retrocear   # además, re-trocea

Sin `--retrocear` solo re-vectoriza los documentos cuyo modelo no es el activo. Con `--retrocear`
vuelve a trocear desde el DoclingDocument guardado (los documentos sin él se saltan y se cuentan).
Las colecciones con paquete nunca se re-trocean (lo buscable es solo lo confirmado): con
`--retrocear` sobre todo el espacio se re-embeben sin re-trocear; nombradas con `--coleccion`, 422.
"""

import argparse
import sys

from app.common.logger import logger
from app.config.database import SessionLocal
from app.models import Coleccion
from app.providers.embeddings import obtener_proveedor_embeddings
from app.services import catalogo
from app.services.reembebido import reembeber_coleccion


def main(argv: list[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    proveedor = obtener_proveedor_embeddings()
    with SessionLocal() as db:
        colecciones = (
            [catalogo.obtener_coleccion(db, argumentos.espacio, argumentos.coleccion)]
            if argumentos.coleccion
            else catalogo.listar_colecciones(db, argumentos.espacio)
        )
        for destino in colecciones:
            coleccion = destino.slug
            retrocear = argumentos.retrocear and _se_puede_retrocear(destino, argumentos)
            resumen = reembeber_coleccion(
                db, argumentos.espacio, coleccion, proveedor, retrocear=retrocear
            )
            logger.info(
                f"{argumentos.espacio}/{coleccion} → {proveedor.modelo_id}: "
                f"documentos {resumen.documentos} · trozos {resumen.trozos} · "
                f"saltados {resumen.saltados} · sin estructura {resumen.sin_estructura}"
            )
    logger.info(f"Colecciones procesadas: {len(colecciones)}")
    return 0


def _se_puede_retrocear(destino: Coleccion, argumentos: argparse.Namespace) -> bool:
    nombrada = argumentos.coleccion is not None
    if destino.paquete is None or nombrada:  # nombrada con paquete: el servicio responde 422
        return True
    logger.warning(
        f"{destino.slug}: tiene paquete «{destino.paquete}», se re-embebe sin re-trocear"
    )
    return False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-embebe colecciones con el proveedor activo.")
    parser.add_argument("--espacio", required=True)
    parser.add_argument("--coleccion", help="sin ella, todas las colecciones del espacio")
    parser.add_argument("--retrocear", action="store_true", help="vuelve a trocear (Docling)")
    return parser


if __name__ == "__main__":
    sys.exit(main())
