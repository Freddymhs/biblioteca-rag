"""Handlers HTTP con tipo de retorno y `type: ignore` con su porqué (chequeo estático por AST)."""

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = sorted((RAIZ / "app" / "routers").glob("*.py")) + [RAIZ / "main.py"]
IGNORE_SIN_MOTIVO = re.compile(r"#\s*type:\s*ignore(\[[^\]]*\])?\s*$")


def test_toda_funcion_declara_su_tipo_de_retorno() -> None:
    sin_tipo = [
        f"{archivo.relative_to(RAIZ)}:{nodo.lineno} {nodo.name}"
        for archivo in ARCHIVOS
        for nodo in ast.walk(ast.parse(archivo.read_text()))
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef) and nodo.returns is None
    ]

    print(f"archivos escaneados: {len(ARCHIVOS)}")
    assert len(ARCHIVOS) > 1
    assert sin_tipo == []


def test_todo_type_ignore_dice_por_que() -> None:
    sin_motivo = [
        f"{archivo.relative_to(RAIZ)}:{numero}"
        for archivo in ARCHIVOS
        for numero, linea in enumerate(archivo.read_text().splitlines(), start=1)
        if IGNORE_SIN_MOTIVO.search(linea)
    ]

    assert sin_motivo == []
