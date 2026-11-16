"""Números y cadenas con significado viven en `app/config/constantes.py` o en `http.HTTPStatus`.

Chequeo estático: el valor no cambia el comportamiento (64 es 64), así que ningún test de
comportamiento distingue un literal de una constante.
"""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

PROHIBIDOS = [
    ("models", r"String\(\d+\)", "largo de columna literal: usar la constante"),
    ("common/errors.py", r"AppError\(\d{3}", "código HTTP literal: usar HTTPStatus"),
    ("common/errors.py", r"status_code=\d{3}", "código HTTP literal: usar HTTPStatus"),
    ("providers/embeddings.py", r"f?\"(ollama|cloudflare):", "prefijo de proveedor: sale del enum"),
]


@pytest.mark.parametrize(("ruta", "patron", "motivo"), PROHIBIDOS, ids=[p[0] for p in PROHIBIDOS])
def test_sin_literales(ruta: str, patron: str, motivo: str) -> None:
    objetivo = APP / ruta
    archivos = sorted(objetivo.rglob("*.py")) if objetivo.is_dir() else [objetivo]
    assert archivos, f"no hay archivos en {objetivo}"

    hallazgos = [
        f"{archivo.relative_to(APP)}:{numero}: {linea.strip()}"
        for archivo in archivos
        for numero, linea in enumerate(archivo.read_text().splitlines(), start=1)
        if re.search(patron, linea)
    ]

    print(f"{ruta}: {len(archivos)} archivos escaneados")
    assert hallazgos == [], f"{motivo}:\n" + "\n".join(hallazgos)
