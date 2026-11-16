"""Comentarios heredados de la plantilla (analogías con Node) ya no describen este proyecto."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = [
    *sorted((RAIZ / "app").rglob("*.py")),
    RAIZ / "main.py",
    RAIZ / "alembic" / "env.py",
    RAIZ / "alembic.ini",
]
ESCOMBRO = re.compile(r"\b(Prisma|Joi|Zod|Express|vitest|template-fastapi|this template)\b", re.I)


def test_sin_comentarios_de_la_plantilla() -> None:
    hallazgos = [
        f"{archivo.relative_to(RAIZ)}:{numero}: {linea.strip()}"
        for archivo in ARCHIVOS
        for numero, linea in enumerate(archivo.read_text().splitlines(), start=1)
        if ESCOMBRO.search(linea)
    ]

    print(f"archivos escaneados: {len(ARCHIVOS)}")
    assert hallazgos == [], "\n".join(hallazgos)
