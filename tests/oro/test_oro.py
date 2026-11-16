"""Preguntas de oro: corren contra una API VIVA con la colección ya ingerida y proveedores reales.

    RAG_ORO_URL=http://localhost:8000 RAG_ORO_ESPACIO=laboral RAG_ORO_API_KEY=<API_KEY> \
        uv run pytest tests/oro -v

`/api/preguntas` es privada desde la FASE_4: sin la clave, cada pregunta responde 401.

Sin `RAG_ORO_URL` solo se valida la forma del archivo (el resto se salta).
"""

import json
import os
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config.constantes import ENCABEZADO_API_KEY

ARCHIVO = Path(__file__).with_name("agricultura.json")
ORO = json.loads(ARCHIVO.read_text(encoding="utf-8"))
URL = os.environ.get("RAG_ORO_URL")
ESPACIO = os.environ.get("RAG_ORO_ESPACIO", "laboral")
CLAVE = os.environ.get("RAG_ORO_API_KEY", "")
TIMEOUT_SEGUNDOS = 180.0

requiere_api = pytest.mark.skipif(URL is None, reason="sin RAG_ORO_URL: no hay API viva")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def test_el_archivo_tiene_la_forma_esperada() -> None:
    preguntas = ORO["preguntas"]
    sin_respuesta = [p for p in preguntas if p["documento"] is None]

    assert len(preguntas) >= 2
    assert len(sin_respuesta) >= 1, "debe haber al menos una pregunta que responda «no lo sé»"
    for pregunta in preguntas:
        assert pregunta["pregunta"].strip()
        assert (pregunta["documento"] is None) == (pregunta["alguna_de"] == [])


@requiere_api
@pytest.mark.parametrize("caso", ORO["preguntas"], ids=lambda caso: caso["pregunta"][:50])
def test_pregunta_de_oro(caso: dict[str, Any]) -> None:
    respuesta = httpx.post(
        f"{URL}/api/preguntas",
        json={"pregunta": caso["pregunta"], "espacio": ESPACIO, "coleccion": ORO["coleccion"]},
        headers={ENCABEZADO_API_KEY: CLAVE},
        timeout=TIMEOUT_SEGUNDOS,
    )
    cuerpo = respuesta.json()
    assert respuesta.status_code == 200, cuerpo

    if caso["documento"] is None:
        assert cuerpo["sabe"] is False, cuerpo["respuesta"]
        return

    citados = {cita["documento"] for cita in cuerpo["citas"]}
    texto = _normalizar(cuerpo["respuesta"])
    assert cuerpo["sabe"] is True, cuerpo["respuesta"]
    assert caso["documento"] in citados, f"citó {citados}"
    assert any(_normalizar(palabra) in texto for palabra in caso["alguna_de"]), cuerpo["respuesta"]
    if caso["pagina"] is not None:
        rangos = [
            (c["pagina_inicio"], c["pagina_fin"])
            for c in cuerpo["citas"]
            if c["documento"] == caso["documento"]
        ]
        dentro = any(inicio <= caso["pagina"] <= fin for inicio, fin in rangos if inicio)
        assert dentro, f"páginas citadas {rangos}"
