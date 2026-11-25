"""Auditoría de la FASE_6, parte K (K1–K6). Cada test falla sin su arreglo."""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.cli import licencias as cli_licencias
from app.config.constantes import (
    MAX_NUMEROS_POR_RANGO_REFERENCIA,
    ROL_PUBLICO,
    RUTA_DOCS,
    SALIDA_CON_ERRORES,
    TROZOS_POR_PREGUNTA,
    OrigenTrozo,
)
from app.models import Documento, Trozo
from app.schemas.documento import MetadatosDocumento
from app.services import pregunta
from app.services.licencias import leer_tabla_licencias
from app.services.metadatos import leer_catalogo
from app.services.pregunta import (
    INSTRUCCIONES,
    Cita,
    _citas_referidas,
    buscar,
    numeros_referidos,
)
from tests.dobles import MODELO_DOBLE, LLMGrabador, proveedor_doble

PREGUNTA = {"pregunta": "¿Kc del olivo?", "espacio": "intereses", "coleccion": "agricultura"}

# ── K1: listas y rangos dentro de un corchete también son referencias ────────

TRES_CITAS = [
    Cita(
        documento_id=numero,
        documento=f"doc-{numero}.txt",
        pagina_inicio=None,
        pagina_fin=None,
        origen=OrigenTrozo.TEXTO,
        fragmento="texto",
        distancia=0.1,
    )
    for numero in (1, 2, 3)
]


@pytest.mark.parametrize(
    ("texto", "esperados"),
    [
        ("Es 0.65 [1, 2].", [1, 2]),
        ("Es 0.65 [1,2].", [1, 2]),
        ("Es 0.65 [ 1 ].", [1]),
        ("Es 0.65 [1-3].", [1, 2, 3]),
        ("Es 0.65 [1–3].", [1, 2, 3]),  # guion largo
        ("Es 0.65 [1;2].", [1, 2]),
        ("Es 0.65 [1][3].", [1, 3]),
        ("Es 0.65 [2, 9].", [2]),  # el 9 no es un fragmento entregado
        ("Es 0.65 [1-999999].", [1, 2, 3]),
        ("Es 0.65 [0].", []),
        ("Es 0.65 [nota 1].", []),
    ],
)
def test_k1_listas_y_rangos_cuentan_como_referencia(texto: str, esperados: list[int]) -> None:
    referidas = _citas_referidas(texto, TRES_CITAS)

    assert [cita.documento_id for cita in referidas] == esperados


def test_k1_un_rango_enorme_no_se_expande_entero() -> None:
    assert len(numeros_referidos("[1-999999]")) == MAX_NUMEROS_POR_RANGO_REFERENCIA


def test_k1_un_numero_de_miles_de_digitos_no_es_referencia() -> None:
    # Python limita int() a 4300 dígitos: sin tope en la regex, esto era un ValueError (500).
    enorme = "9" * 5000

    assert numeros_referidos(f"[{enorme}]") == set()
    assert numeros_referidos(f"[1-{enorme}]") == set()


@pytest.mark.usefixtures("biblioteca_publica")
def test_k1_una_lista_en_un_corchete_responde_con_cita(
    client: TestClient, llm: LLMGrabador
) -> None:
    llm.respuesta = "El Kc del olivo es 0.65 [1, 2]."

    cuerpo = client.post("/api/preguntas", json=PREGUNTA).json()

    assert cuerpo["sabe"] is True and cuerpo["citas"]


def test_k1_las_instrucciones_piden_un_numero_por_corchete() -> None:
    assert "[1][2]" in INSTRUCCIONES and "[1, 2]" in INSTRUCCIONES


# ── K2: ordenar y cortar sobre los ids, y unir solo esos ─────────────────────

TROZOS_DE_MAS = 30  # bastante más que TROZOS_POR_PREGUNTA, todos dentro del filtro


def _trozos_de_mas(db: Session) -> list[float]:
    vector = proveedor_doble().cliente.embed_query("riego del olivo")
    documento = db.scalar(select(Documento.id).where(Documento.nombre_archivo == "olivo.txt"))
    for orden in range(TROZOS_DE_MAS):
        db.add(
            Trozo(
                documento_id=documento,
                orden=1000 + orden,
                texto="otro trozo del olivo",
                embedding=vector,
                embedding_model=MODELO_DOBLE,
            )
        )
    db.flush()
    return vector


def _filas_unidas_en_la_busqueda(db: Session, buscar_ahora: Callable[[], object]) -> list[int]:
    """Las filas que produce cada JOIN de la consulta principal de `buscar` (EXPLAIN ANALYZE de
    la consulta tal como llegó al driver). No cuenta la CTE ni las subconsultas iniciales."""
    conexion = db.connection()
    capturadas: list[tuple[str, object]] = []

    def capturar(_c: object, _cur: object, sql: str, parametros: object, *_: object) -> None:
        if "filtrados" in sql:
            capturadas.append((sql, parametros))

    event.listen(conexion, "before_cursor_execute", capturar)
    try:
        buscar_ahora()
    finally:
        event.remove(conexion, "before_cursor_execute", capturar)
    sql, parametros = capturadas[-1]
    plan = conexion.exec_driver_sql(
        f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}",
        parametros,  # type: ignore[arg-type]  # los del driver
    ).scalar_one()[0]["Plan"]
    return list(_filas_de_los_joins(plan))


def _filas_de_los_joins(nodo: dict) -> Iterator[int]:
    if "Join Type" in nodo:
        yield nodo["Actual Rows"] * nodo["Actual Loops"]
    for hijo in nodo.get("Plans", []):
        if hijo.get("Parent Relationship") not in ("InitPlan", "SubPlan"):
            yield from _filas_de_los_joins(hijo)


@pytest.mark.usefixtures("biblioteca_publica")
@pytest.mark.parametrize("publico", [False, True], ids=["privada", "publica"])
def test_k2_la_busqueda_une_solo_los_trozos_que_devuelve(db: Session, publico: bool) -> None:
    vector = _trozos_de_mas(db)

    def buscar_ahora() -> object:
        if not publico:
            return buscar(db, vector, "intereses", "agricultura", MODELO_DOBLE)
        db.execute(text(f"SET LOCAL ROLE {ROL_PUBLICO}"))
        return buscar(db, vector, "intereses", "agricultura", MODELO_DOBLE, solo_publico=True)

    filas = _filas_unidas_en_la_busqueda(db, buscar_ahora)
    db.execute(text("RESET ROLE"))

    print(f"filas por JOIN: {filas}")
    assert filas, "la consulta no tiene ningún JOIN: el chequeo no mide nada"
    assert max(filas) <= TROZOS_POR_PREGUNTA


# ── K3: el comando de licencias, más estricto ────────────────────────────────

CABECERA = "| # | Archivo | Propuesta | Veredicto |\n|---|---|---|---|\n"
FILA_OLIVO = "| 1 | olivo.txt | CC BY 4.0 | publicar (Freddy, 2026-11-16) |\n"
FILA_PODA = "| 2 | poda.txt | Todos los derechos reservados | no publicar: derechos reservados |\n"


def _tabla(tmp_path: Path, contenido: str) -> Path:
    ruta = tmp_path / "licencias.md"
    ruta.write_text(contenido)
    return ruta


def test_k3_un_archivo_repetido_se_rechaza_nombrandolo(tmp_path: Path) -> None:
    ruta = _tabla(tmp_path, CABECERA + FILA_OLIVO + FILA_OLIVO.replace("| 1 |", "| 3 |"))

    with pytest.raises(ValueError, match=r"olivo\.txt"):
        leer_tabla_licencias(ruta)


@pytest.mark.parametrize(
    "veredicto", ["publicarlo después", "publicar?", "no se", "publicar o no publicar"]
)
def test_k3_un_veredicto_que_no_es_una_forma_conocida_se_rechaza(
    tmp_path: Path, veredicto: str
) -> None:
    ruta = _tabla(tmp_path, CABECERA + f"| 1 | olivo.txt | CC BY 4.0 | {veredicto} |\n")

    with pytest.raises(ValueError, match="línea 3"):
        leer_tabla_licencias(ruta)


def test_k3_las_formas_conocidas_publican_o_no(tmp_path: Path) -> None:
    ruta = _tabla(tmp_path, CABECERA + FILA_OLIVO + FILA_PODA)

    filas = leer_tabla_licencias(ruta)

    assert [(f.archivo, f.publicar) for f in filas] == [("olivo.txt", True), ("poda.txt", False)]


def test_k3_solo_se_lee_la_tabla_bajo_su_cabecera(tmp_path: Path) -> None:
    otra = "\nNotas al pie:\n\n| Columna | Otra |\n|---|---|\n| x | y |\n"
    ruta = _tabla(tmp_path, "# Licencias\n\n" + CABECERA + FILA_OLIVO + otra)

    filas = leer_tabla_licencias(ruta)

    assert [f.archivo for f in filas] == ["olivo.txt"]


@pytest.mark.parametrize(
    "fila",
    [
        "| 1 | olivo.txt | CC BY 4.0 |\n",
        "| 1 | olivo.txt || publicar |\n",
        "| 1 | | X | publicar |\n",
    ],
    ids=["celda-de-menos", "propuesta-vacia", "archivo-vacio"],
)
def test_k3_una_fila_mal_formada_se_rechaza_nombrando_la_linea(tmp_path: Path, fila: str) -> None:
    ruta = _tabla(tmp_path, CABECERA + fila)

    with pytest.raises(ValueError, match="línea 3"):
        leer_tabla_licencias(ruta)


def _correr_licencias(db: Session, tabla: Path, *extra: str) -> int:
    argumentos = ["--tabla", str(tabla), "--espacio", "intereses", "--coleccion", "agricultura"]
    return cli_licencias.main_con([*argumentos, *extra], abrir_sesion=lambda: nullcontext(db))


@pytest.mark.usefixtures("biblioteca_publica")
def test_k3_si_ninguna_fila_calza_sale_con_error(db: Session, tmp_path: Path) -> None:
    ruta = _tabla(tmp_path, CABECERA + FILA_OLIVO.replace("olivo.txt", "no-esta.pdf"))

    assert _correr_licencias(db, ruta) == SALIDA_CON_ERRORES


@pytest.mark.usefixtures("biblioteca_publica")
def test_k3_al_aplicar_con_filas_sin_documento_sale_con_error(db: Session, tmp_path: Path) -> None:
    falta = FILA_OLIVO.replace("olivo.txt", "no-esta.pdf").replace("| 1 |", "| 3 |")
    ruta = _tabla(tmp_path, CABECERA + FILA_OLIVO + falta)

    assert _correr_licencias(db, ruta) == 0  # sin --aplicar solo informa
    assert _correr_licencias(db, ruta, "--aplicar") == SALIDA_CON_ERRORES


# ── K4: títulos y fuentes en blanco o con caracteres de control ──────────────

URL_DOCS = "/api/espacios/intereses/colecciones/agricultura/documentos"


def test_k4_los_metadatos_se_recortan_y_lo_blanco_es_ausente() -> None:
    metadatos = MetadatosDocumento(titulo="  Manual del olivo  ", fuente=" \t ")

    assert (metadatos.titulo, metadatos.fuente) == ("Manual del olivo", None)


@pytest.mark.usefixtures("biblioteca_publica")
def test_k4_al_subir_un_titulo_en_blanco_es_sin_titulo(client: TestClient) -> None:
    datos = {"titulo": "   ", "fuente": "  INIA  "}
    archivo = ("blanco.txt", b"Riego del olivo en blanco")

    subido = client.post(URL_DOCS, files={"archivo": archivo}, data=datos).json()

    assert (subido["titulo"], subido["fuente"]) == (None, "INIA")


@pytest.mark.usefixtures("biblioteca_publica")
@pytest.mark.parametrize("valor", ["Manual\x00del olivo", "Manual\x07", "Manual\ndel olivo"])
@pytest.mark.parametrize("campo", ["titulo", "fuente"])
def test_k4_un_caracter_de_control_es_422(client: TestClient, campo: str, valor: str) -> None:
    archivo = ("control.txt", b"Riego del olivo con control")

    respuesta = client.post(URL_DOCS, files={"archivo": archivo}, data={campo: valor})

    assert respuesta.status_code == 422


def test_k4_el_catalogo_rechaza_un_caracter_de_control_nombrando_la_entrada(
    tmp_path: Path,
) -> None:
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps([{"archivo": "a.pdf", "titulo": "Manual\u0000"}]))

    with pytest.raises(ValueError, match=r"a\.pdf"):
        leer_catalogo(ruta)


def test_k4_en_el_catalogo_un_titulo_en_blanco_es_sin_titulo(tmp_path: Path) -> None:
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps({"a.pdf": {"titulo": "  ", "fuente": " INIA "}}))

    metadatos = leer_catalogo(ruta)["a.pdf"]

    assert (metadatos.titulo, metadatos.fuente) == (None, "INIA")


# ── K5: el log de arranque no anuncia /docs si está cerrada ──────────────────

SONDA_ARRANQUE = """
from fastapi.testclient import TestClient
from main import app
with TestClient(app):
    pass
"""


@pytest.mark.parametrize(("valor", "anuncia"), [("false", False), ("true", True)])
def test_k5_el_log_de_arranque_anuncia_docs_solo_si_esta_abierta(valor: str, anuncia: bool) -> None:
    """Proceso aparte: la app se arma al importarse, con la configuración de ese momento."""
    entorno = {
        **os.environ,
        "DOCUMENTACION_API": valor,
        "DATABASE_URL_PUBLICA": "",
        "PERMITIR_PUBLICO_SIN_USUARIO": "true",
        "LOG_LEVEL": "INFO",
    }

    salida = subprocess.run(
        [sys.executable, "-c", SONDA_ARRANQUE],
        env=entorno,
        capture_output=True,
        text=True,
        check=True,
    )
    arranque = next(linea for linea in salida.stdout.splitlines() if "started" in linea)

    assert (RUTA_DOCS in arranque) is anuncia


# ── K6: sin comentarios duplicados ───────────────────────────────────────────


def test_k6_el_comentario_b5_de_pregunta_aparece_una_vez() -> None:
    fuente = Path(pregunta.__file__).read_text(encoding="utf-8")

    assert sum(linea.startswith("# B5") for linea in fuente.splitlines()) == 1
