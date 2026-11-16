"""C13: restos que ningún test de comportamiento ve (chequeo estático, imprime su denominador)."""

import ast
import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_las_migraciones_no_traen_el_comentario_de_autogenerate() -> None:
    migraciones = sorted((RAIZ / "alembic" / "versions").glob("*.py"))
    con_resto = [m.name for m in migraciones if "please adjust" in m.read_text()]

    print(f"migraciones escaneadas: {len(migraciones)}")
    assert len(migraciones) > 1
    assert con_resto == []


def _modulos_importados(archivo: Path) -> set[str]:
    """Los imports reales (por AST): un comentario que nombra el módulo no cuenta."""
    modulos: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text())):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module.split(".")[0])
    return modulos


def test_python_dotenv_no_se_declara_si_nadie_lo_importa() -> None:
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]
    declaradas = {re.split(r"[<>=\[ ]", dep)[0] for dep in proyecto["dependencies"]}
    fuentes = [*RAIZ.glob("app/**/*.py"), *RAIZ.glob("alembic/**/*.py"), RAIZ / "main.py"]
    importados = set().union(*(_modulos_importados(fuente) for fuente in fuentes))

    print(f"fuentes escaneadas: {len(fuentes)}")
    assert "python-dotenv" not in declaradas or "dotenv" in importados


def test_los_helpers_de_los_tests_declaran_su_tipo_de_retorno() -> None:
    archivos = sorted((RAIZ / "tests").rglob("*.py"))
    sin_tipo = [
        f"{archivo.relative_to(RAIZ)}:{nodo.lineno} {nodo.name}"
        for archivo in archivos
        for nodo in ast.walk(ast.parse(archivo.read_text()))
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef)
        and nodo.name.startswith("_")
        and nodo.returns is None
    ]

    print(f"archivos de tests escaneados: {len(archivos)}")
    assert sin_tipo == [], "\n".join(sin_tipo)
