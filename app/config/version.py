"""La versión vive solo en `pyproject.toml`; aquí se lee, no se repite."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def leer_version(pyproject: Path = PYPROJECT) -> str:
    with pyproject.open("rb") as archivo:
        return tomllib.load(archivo)["project"]["version"]


VERSION = leer_version()
