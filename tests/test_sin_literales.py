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
    # Auditoría FASE_5, I10
    (
        "observabilidad.py",
        r"\"(http\.response\.status_code|error\.type)\"",
        "atributo: AtributoTraza",
    ),
    ("observabilidad.py", r"^[A-Z_]+ = ", "constante de módulo: va en constantes.py"),
    ("providers/limites.py", r"\"429\"", "sufijo de contador que se confunde con el código HTTP"),
    ("routers/uso.py", r"^[A-Z_]+ = \d", "días por defecto: va en constantes.py"),
]


def test_un_dia_en_segundos_se_define_una_vez() -> None:
    """I10: VENTANA_DIARIA_SEGUNDOS y SEGUNDOS_POR_DIA repetían el mismo cálculo."""
    constantes = (APP / "config" / "constantes.py").read_text()

    assert constantes.count("24 * 60 * 60") == 1


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
