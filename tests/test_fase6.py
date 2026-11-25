"""FASE_6: decisiones de Freddy del 2026-11-16. Cada test falla sin su cambio."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config.constantes import RESPUESTA_NO_LO_SE
from app.models import Documento, Trozo
from tests.dobles import MODELO_DOBLE, LLMGrabador, proveedor_doble

pytestmark = pytest.mark.usefixtures("biblioteca_publica")
PREGUNTA = {"pregunta": "¿Kc del olivo?", "espacio": "intereses", "coleccion": "agricultura"}


# ── 6.2: sin una referencia [n] válida no hay respuesta ──────────────────────


@pytest.mark.parametrize(
    "redactada",
    ["El Kc del olivo es 0.65.", "El Kc del olivo es 0.65 [9].", "Según [0], es 0.65."],
    ids=["sin-referencia", "referencia-inexistente", "referencia-cero"],
)
def test_62_sin_referencia_valida_es_no_lo_se(
    client: TestClient, llm: LLMGrabador, redactada: str
) -> None:
    llm.respuesta = redactada

    cuerpo = client.post("/api/preguntas", json=PREGUNTA).json()

    assert (cuerpo["sabe"], cuerpo["respuesta"], cuerpo["citas"]) == (
        False,
        RESPUESTA_NO_LO_SE,
        [],
    )


def test_62_con_una_referencia_valida_responde_y_cita_solo_esa(
    client: TestClient, llm: LLMGrabador
) -> None:
    llm.respuesta = "El Kc del olivo es 0.65 [1]."

    cuerpo = client.post("/api/preguntas", json=PREGUNTA).json()

    assert cuerpo["sabe"] is True and len(cuerpo["citas"]) == 1


# ── 6.1: título, fuente y año en el documento y en la cita ───────────────────

URL_DOCS = "/api/espacios/intereses/colecciones/agricultura/documentos"
METADATOS = {"titulo": "Manual del olivo en el valle", "fuente": "INIA Chile", "anno": "2019"}
CORPUS = Path("/home/fmarcosdev/Volumes/Extended/github/PRODUCTION/BIBLIOTECAPARARAG-AGRICULTURA")


def _subir(client: TestClient, nombre: str, texto: str, datos: dict | None = None) -> dict:
    archivo = (nombre, texto.encode())
    return client.post(URL_DOCS, files={"archivo": archivo}, data=datos or {}).json()


def test_61_la_cita_muestra_el_titulo_que_llego_al_subir(
    client: TestClient, llm: LLMGrabador
) -> None:
    subido = _subir(client, "tuna.txt", "Tuna y cochinilla en el valle.", METADATOS)
    llm.respuesta = "Se cultiva con cochinilla [1]."

    cuerpo = client.post(
        "/api/preguntas", json={**PREGUNTA, "pregunta": "¿tuna y cochinilla?"}
    ).json()
    cita = next(c for c in cuerpo["citas"] if c["documento"] == "tuna.txt")

    assert (subido["titulo"], subido["fuente"], subido["anno"]) == (
        "Manual del olivo en el valle",
        "INIA Chile",
        2019,
    )
    assert (cita["titulo"], cita["fuente"], cita["anno"]) == (
        "Manual del olivo en el valle",
        "INIA Chile",
        2019,
    )
    assert "Manual del olivo en el valle" in llm.recibidos[-1][-1].text  # el LLM ve el título


def test_61_sin_titulo_la_cita_cae_al_nombre_del_archivo(client: TestClient) -> None:
    cuerpo = client.post("/api/preguntas", json=PREGUNTA).json()

    assert cuerpo["citas"][0]["titulo"] == cuerpo["citas"][0]["documento"] == "olivo.txt"


def test_61_la_busqueda_publica_tambien_trae_el_titulo(
    client: TestClient, anonimo: TestClient
) -> None:
    """El rol público lee `documento` por columnas concedidas: sin el GRANT, esto falla."""
    subido = _subir(client, "riego.txt", "Riego del olivo con kc 0.7 en verano.", METADATOS)
    client.put(f"{URL_DOCS}/{subido['id']}/licencia", json={"licencia": "X", "verificada": True})

    fragmentos = anonimo.get("/api/publico/buscar", params={"q": "riego kc verano"}).json()

    titulos = {f["titulo"] for f in fragmentos["fragmentos"]}
    assert "Manual del olivo en el valle" in titulos


@pytest.mark.parametrize(
    ("campo", "valor"), [("anno", "999"), ("anno", "2101"), ("titulo", "x" * 501)]
)
def test_61_metadatos_fuera_de_rango_son_422(client: TestClient, campo: str, valor: str) -> None:
    respuesta = client.post(
        URL_DOCS, files={"archivo": ("a.txt", b"Riego del olivo")}, data={campo: valor}
    )

    assert respuesta.status_code == 422


def test_61_un_titulo_vacio_es_sin_titulo(client: TestClient) -> None:
    """FastAPI convierte un campo de formulario vacío en None: la cita cae al nombre del archivo."""
    subido = _subir(client, "a.txt", "Riego del olivo", {"titulo": ""})

    assert subido["titulo"] is None


@pytest.mark.parametrize("forma", ["lista", "mapa"])
def test_61_la_cli_toma_los_metadatos_de_un_catalogo(
    tmp_path: Path, db: Session, forma: str
) -> None:
    from contextlib import nullcontext

    from app.cli import ingestar as cli
    from tests.dobles import proveedor_doble

    (tmp_path / "riego.txt").write_text("Riego del olivo con kc 0.7.")
    (tmp_path / "poda.txt").write_text("Poda del olivo en invierno.")  # no está en el catálogo
    entrada = {"titulo": "Riego en el valle", "fuente": "INIA", "anno": 2020, "region": "x"}
    catalogo = [{"archivo": "riego.txt", **entrada}] if forma == "lista" else {"riego.txt": entrada}
    ruta_catalogo = tmp_path / "catalogo.json"
    ruta_catalogo.write_text(json.dumps(catalogo))

    cli.main_con(
        [str(tmp_path), "--espacio", "intereses", "--coleccion", "agricultura",
         "--catalogo", str(ruta_catalogo), "--excluir", "catalogo.json"],
        abrir_sesion=lambda: nullcontext(db),
        obtener_proveedor=proveedor_doble,
        vision=None,
    )  # fmt: skip
    metadatos = {
        d.nombre_archivo: (d.titulo, d.fuente, d.anno)
        for d in db.scalars(
            select(Documento).where(Documento.nombre_archivo.in_(["riego.txt", "poda.txt"]))
        )
    }

    assert metadatos == {
        "riego.txt": ("Riego en el valle", "INIA", 2020),
        "poda.txt": (None, None, None),
    }


def test_61_un_catalogo_invalido_se_rechaza_nombrando_la_entrada(tmp_path: Path) -> None:
    from app.services.metadatos import leer_catalogo

    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps([{"archivo": "a.pdf", "anno": "no es año"}]))

    with pytest.raises(ValueError, match="a.pdf"):
        leer_catalogo(ruta)


@pytest.mark.skipif(not (CORPUS / "catalogo.json").exists(), reason="sin el corpus local")
def test_61_el_catalogo_real_de_agricultura_se_lee_entero() -> None:
    """Solo lectura: el formato real (lista, con campos extra) se entiende sin código específico."""
    from app.services.metadatos import leer_catalogo

    catalogo = leer_catalogo(CORPUS / "catalogo.json")

    assert len(catalogo) == 89 and all(m.titulo for m in catalogo.values())


# ── 6.4: la documentación interactiva, cerrada en producción ─────────────────

SONDA_DOCS = """
from fastapi.testclient import TestClient
from main import app
c = TestClient(app)
print(*[c.get(r).status_code for r in ("/docs", "/redoc", "/openapi.json", "/health")])
"""


@pytest.mark.parametrize(
    ("valor", "esperado"), [("false", "404 404 404 200"), ("true", "200 200 200 200")]
)
def test_64_docs_redoc_y_openapi_dependen_de_la_configuracion(valor: str, esperado: str) -> None:
    """Proceso aparte: la app se arma al importarse, con la configuración de ese momento."""
    entorno = {**os.environ, "DOCUMENTACION_API": valor, "PERMITIR_PUBLICO_SIN_USUARIO": "true"}

    salida = subprocess.run(
        [sys.executable, "-c", SONDA_DOCS], env=entorno, capture_output=True, text=True, check=True
    )

    assert salida.stdout.strip().splitlines()[-1] == esperado


def test_64_produccion_la_cierra() -> None:
    raiz = Path(__file__).resolve().parent.parent
    texto = (raiz / "docker-compose.prod.yml").read_text()

    assert 'DOCUMENTACION_API: "false"' in texto


# ── 6.7: licencias desde la tabla con el veredicto ───────────────────────────

TABLA_LICENCIAS = """# Licencias

| # | Archivo | Fuente (catálogo) | Páginas leídas | Evidencia | Propuesta | Veredicto |
|---|---|---|---|---|---|---|
| 1 | olivo.txt | INIA | completo | — | CC BY 4.0 | publicar (Freddy, 2026-11-16) |
| 2 | poda.txt | INIA | p1-4 | «…» | Todos los derechos reservados | no publicar (Freddy) |
| 3 | no-esta.pdf | X | p1-4 | — | CC BY 4.0 | publicar (Freddy, 2026-11-16) |
"""
TABLA_REAL = (
    Path(__file__).resolve().parent.parent / "docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md"
)


def _licencias(db: Session) -> dict[str, tuple[str | None, bool]]:
    consulta = select(Documento.nombre_archivo, Documento.licencia, Documento.licencia_verificada)
    return {nombre: (licencia, verificada) for nombre, licencia, verificada in db.execute(consulta)}


def _correr_licencias(db: Session, tabla: Path, *extra: str) -> int:
    from contextlib import nullcontext

    from app.cli import licencias as cli

    argumentos = ["--tabla", str(tabla), "--espacio", "intereses", "--coleccion", "agricultura"]
    return cli.main_con([*argumentos, *extra], abrir_sesion=lambda: nullcontext(db))


def test_67_sin_aplicar_no_cambia_nada(db: Session, tmp_path: Path) -> None:
    tabla = tmp_path / "t.md"
    tabla.write_text(TABLA_LICENCIAS)
    antes = _licencias(db)

    _correr_licencias(db, tabla)

    assert _licencias(db) == antes


def test_67_con_aplicar_verifica_lo_que_dice_publicar_y_solo_eso(
    db: Session, tmp_path: Path
) -> None:
    tabla = tmp_path / "t.md"
    tabla.write_text(TABLA_LICENCIAS)

    _correr_licencias(db, tabla, "--aplicar")
    despues = _licencias(db)

    assert despues["olivo.txt"] == ("CC BY 4.0", True)
    licencia_poda, verificada_poda = despues["poda.txt"]
    assert verificada_poda is False  # derechos reservados: queda sin publicar
    assert (licencia_poda or "").startswith("Todos los derechos reservados")


def test_67_la_tabla_real_tiene_79_a_publicar_y_10_no() -> None:
    from app.services.licencias import leer_tabla_licencias

    filas = leer_tabla_licencias(TABLA_REAL)

    assert len(filas) == 89
    assert sum(fila.publicar for fila in filas) == 79
    assert all(not f.publicar for f in filas if f.propuesta.startswith("Todos los derechos"))


# ── 6.3: la búsqueda con filtros no depende del recorrido HNSW ───────────────

VECINOS_PRIVADOS = 200  # más que hnsw.ef_search (40): HNSW no llega a los de la colección


def _vecinos_privados(db: Session, texto: str) -> None:
    """Muchos trozos privados casi idénticos a `texto`, en la colección privada `sobre-mi`."""
    vector = proveedor_doble().cliente.embed_query(texto)
    documento = db.scalar(select(Documento.id).where(Documento.nombre_archivo == "potasio.txt"))
    for orden in range(VECINOS_PRIVADOS):
        db.add(
            Trozo(
                documento_id=documento,
                orden=1000 + orden,
                texto="vecino privado",
                embedding=vector,
                embedding_model=MODELO_DOBLE,
            )
        )
    db.flush()
    # Lo que pasará con muchos datos, exagerado: el planificador prefiere CUALQUIER índice a
    # recorrer la tabla, a un bitmap o a ordenar. Sin 6.3 eso elige HNSW, que filtra después.
    for ajuste in ("enable_seqscan", "enable_bitmapscan", "enable_sort"):
        db.execute(text(f"SET LOCAL {ajuste} = off"))


def test_63_lo_publico_encuentra_lo_suyo_aunque_los_vecinos_sean_privados(
    anonimo: TestClient, db: Session
) -> None:
    _vecinos_privados(db, "riego del olivo")

    fragmentos = anonimo.get("/api/publico/buscar", params={"q": "riego del olivo"}).json()

    assert [f["documento"] for f in fragmentos["fragmentos"]] == ["olivo.txt"]


def test_63_lo_privado_encuentra_lo_de_su_coleccion_aunque_haya_vecinos_en_otra(
    client: TestClient, db: Session
) -> None:
    _vecinos_privados(db, "riego del olivo")
    cuerpo = {"pregunta": "riego del olivo", "espacio": "intereses", "coleccion": "agricultura"}

    citas = client.post("/api/preguntas", json=cuerpo).json()["citas"]

    assert {c["documento"] for c in citas} == {"olivo.txt"}


def test_63_el_trigger_completa_espacio_y_coleccion_del_trozo(db: Session) -> None:
    from app.models import Coleccion

    trozo = db.scalars(
        select(Trozo).join(Documento).where(Documento.nombre_archivo == "olivo.txt")
    ).first()
    assert trozo is not None
    coleccion = db.get_one(Coleccion, trozo.coleccion_id)

    assert (coleccion.slug, coleccion.espacio_id) == ("agricultura", trozo.espacio_id)


# ── 6.6: el navegador del portal llama a lo público ──────────────────────────

ORIGEN_PORTAL = "https://portal.agriplan.example"
SONDA_CORS = """
import os
from fastapi.testclient import TestClient
from main import app
c = TestClient(app)
portal = os.environ["ORIGEN_DE_PRUEBA"]
def preflight(origen):
    r = c.options("/api/publico/preguntas", headers={
        "Origin": origen, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    return r.headers.get("access-control-allow-origin")
salud = c.get("/health", headers={"Origin": portal})
expuestos = salud.headers.get("access-control-expose-headers")
print(preflight(portal), preflight("https://otro.example"), expuestos)
"""


def test_66_cors_deja_pasar_al_portal_configurado_y_a_nadie_mas() -> None:
    entorno = {
        **os.environ,
        "CORS_ORIGINS": json.dumps([ORIGEN_PORTAL]),
        "ORIGEN_DE_PRUEBA": ORIGEN_PORTAL,
        "PERMITIR_PUBLICO_SIN_USUARIO": "true",
    }

    salida = subprocess.run(
        [sys.executable, "-c", SONDA_CORS], env=entorno, capture_output=True, text=True, check=True
    )
    permitido, otro, expuestos = salida.stdout.strip().splitlines()[-1].split(" ", 2)

    assert (permitido, otro) == (ORIGEN_PORTAL, "None")
    assert "x-traza-id" in expuestos.lower()  # el portal puede leer el id de la traza
