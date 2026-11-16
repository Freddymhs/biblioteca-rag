from pathlib import Path

from app.config.version import leer_version


def test_la_version_sale_de_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "9.8.7"\n')

    assert leer_version(pyproject) == "9.8.7"


def test_la_app_publica_la_version_del_proyecto() -> None:
    from main import app

    assert app.version == leer_version()
