"""Precarga los modelos de Docling (layout, tablas) y el tokenizador de los trozos (B6).

    uv run python -m app.cli.precargar_modelos

La corre el Dockerfile al construir la imagen; fuera de Docker, la primera subida los baja sola.
"""

import sys

from app.common.logger import logger
from app.services.extraccion import precargar_modelos


def main() -> int:
    precargar_modelos()
    logger.info("Modelos de Docling y tokenizador listos en la caché")
    return 0


if __name__ == "__main__":
    sys.exit(main())
