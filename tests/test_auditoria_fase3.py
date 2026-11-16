"""Auditoría de la FASE_3, parte E (E1–E12). Cada test falla sin su arreglo."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.common.errors import AppError, service_unavailable
from app.config.constantes import EstadoExtraccion, OrigenTrozo, TipoDecision
from app.dominio.base import HerramientaSQL, ResultadoCalculo
from app.dominio.facturas import FACTURAS, Factura, FiltroFacturas, FiltroPorEmisor
from app.models import Documento, Extraccion, Trozo
from app.services import catalogo
from tests.dobles import FACTURA_OLIVOS, ExtractorDoble, RespuestaHTTP, proveedor_doble

RAIZ = Path(__file__).resolve().parent.parent
FACTURAS_URL = "/api/espacios/laboral/colecciones/facturas"


@pytest.fixture(autouse=True)
def colecciones(client: TestClient) -> None:
    client.post("/api/espacios", json={"slug": "laboral", "nombre": "Laboral"})
    for slug, paquete in (("facturas", "facturas"), ("otras", "facturas"), ("notas", None)):
        cuerpo = {"slug": slug, "nombre": slug, "paquete": paquete}
        client.post("/api/espacios/laboral/colecciones", json=cuerpo)


def _subir(
    client: TestClient, extractor: ExtractorDoble, datos: dict, coleccion: str = "facturas"
) -> int:
    extractor.datos = datos
    contenido = f"Factura {datos['numero']} de {datos['emisor']} {datos['moneda']}".encode()
    archivo = ("f.txt", contenido)
    url = f"/api/espacios/laboral/colecciones/{coleccion}/documentos"
    return client.post(url, files={"archivo": archivo}).json()["extraccion_id"]


def _confirmar(client: TestClient, extraccion_id: int, datos: dict) -> RespuestaHTTP:
    return client.post(f"/api/extracciones/{extraccion_id}/confirmacion", json=datos)


def _cargar(
    client: TestClient, extractor: ExtractorDoble, datos: dict, coleccion: str = "facturas"
) -> int:
    extraccion_id = _subir(client, extractor, datos, coleccion)
    _confirmar(client, extraccion_id, datos)
    return extraccion_id


def _ejecutar(
    db: Session, nombre: str, argumentos: BaseModel, coleccion: str = "facturas"
) -> ResultadoCalculo:
    herramienta = FACTURAS.herramienta(nombre)
    assert herramienta is not None
    destino = catalogo.obtener_coleccion(db, "laboral", coleccion)
    return herramienta.ejecutar(db, destino.id, FACTURAS.nombre, argumentos)


# ── E1: re-trocear no expone lo no confirmado ─────────────────────────────────


def test_e1_no_se_retrocea_una_coleccion_con_paquete(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    from app.services.reembebido import reembeber_coleccion

    _subir(client, extractor, FACTURA_OLIVOS)  # pendiente: tiene estructura de Docling, sin trozos

    with pytest.raises(AppError) as error:
        reembeber_coleccion(db, "laboral", "facturas", proveedor_doble(), retrocear=True)

    assert error.value.status_code == 422
    assert db.scalar(select(func.count()).select_from(Trozo)) == 0


def test_e1_reembeber_conserva_el_trozo_de_datos_y_no_toca_lo_pendiente(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    from app.services.reembebido import reembeber_coleccion

    _cargar(client, extractor, FACTURA_OLIVOS)
    _subir(client, extractor, {**FACTURA_OLIVOS, "numero": "88"})  # pendiente

    reembeber_coleccion(db, "laboral", "facturas", proveedor_doble(modelo_id="otro:modelo"))

    trozos = db.scalars(select(Trozo)).all()
    assert [(t.origen, t.embedding_model) for t in trozos] == [(OrigenTrozo.DATOS, "otro:modelo")]


# ── E2: dos confirmaciones en paralelo ───────────────────────────────────────


def test_e2_si_otra_confirmacion_gana_mientras_se_embebe_es_409_y_no_sobrescribe(
    client: TestClient, db: Session, extractor: ExtractorDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import dominio

    extraccion_id = _subir(client, extractor, FACTURA_OLIVOS)
    ganadora = {**FACTURA_OLIVOS, "total": "1"}
    embeber_real = dominio.embeber_documentos

    def embeber_mientras_otra_confirma(proveedor, textos):  # noqa: ANN001, ANN202 — espía
        db.execute(
            update(Extraccion)
            .where(Extraccion.id == extraccion_id)
            .values(estado=EstadoExtraccion.CONFIRMADA, confirmados=ganadora)
        )
        db.commit()
        return embeber_real(proveedor, textos)

    monkeypatch.setattr(dominio, "embeber_documentos", embeber_mientras_otra_confirma)

    respuesta = _confirmar(client, extraccion_id, FACTURA_OLIVOS)

    assert respuesta.status_code == 409
    db.expire_all()
    assert db.get_one(Extraccion, extraccion_id).confirmados == ganadora


# ── E3: sin datos confirmados no es un dato ───────────────────────────────────


def test_e3_sin_facturas_confirmadas_el_calculo_no_sabe(
    client: TestClient, extractor: ExtractorDoble
) -> None:
    from app.providers.estructurado import Decision, obtener_clasificador
    from main import app

    _subir(client, extractor, FACTURA_OLIVOS)  # solo pendiente
    app.dependency_overrides[obtener_clasificador] = lambda: (
        lambda *_a: Decision(tipo=TipoDecision.CALCULO, herramienta="cantidad_de_facturas")
    )

    cuerpo = client.post(
        "/api/preguntas",
        json={"pregunta": "¿Cuántas facturas?", "espacio": "laboral", "coleccion": "facturas"},
    ).json()

    assert (cuerpo["ruta"], cuerpo["sabe"], cuerpo["citas"]) == ("sql", False, [])
    assert "No hay facturas confirmadas" in cuerpo["respuesta"]


# ── E4: ranking y máximo por moneda ──────────────────────────────────────────

EN_USD = {
    **FACTURA_OLIVOS,
    "numero": "U1",
    "emisor": "Importadora",
    "moneda": "USD",
    "total": "1000",
}
EN_CLP = {
    **FACTURA_OLIVOS,
    "numero": "C1",
    "emisor": "Ferreteria",
    "moneda": "CLP",
    "total": "5000",
}


def test_e4_la_factura_mas_alta_y_el_ranking_son_por_moneda(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    _cargar(client, extractor, EN_USD)
    _cargar(client, extractor, EN_CLP)

    mas_alta = _ejecutar(db, "factura_mas_alta", FiltroFacturas()).respuesta
    ranking = _ejecutar(db, "facturado_por_emisor", FiltroPorEmisor(limite=1)).respuesta

    assert "1.000 USD" in mas_alta and "5.000 CLP" in mas_alta
    assert "Importadora" in ranking and "Ferreteria" in ranking  # el primero de CADA moneda


# ── E5: subir sin paquete no necesita LLM ────────────────────────────────────


def test_e5_subir_a_una_coleccion_sin_paquete_no_instancia_el_extractor(client: TestClient) -> None:
    from app.providers.estructurado import obtener_fabrica_extractor
    from main import app

    def sin_llm():  # noqa: ANN202 — fábrica que falla como sin llave configurada
        raise service_unavailable("LLM sin configurar")

    app.dependency_overrides[obtener_fabrica_extractor] = lambda: sin_llm
    sin_paquete = client.post(
        "/api/espacios/laboral/colecciones/notas/documentos", files={"archivo": ("n.txt", b"hola")}
    )
    con_paquete = client.post(
        f"{FACTURAS_URL}/documentos", files={"archivo": ("f.txt", b"Factura 1")}
    )

    assert sin_paquete.status_code == 201
    assert con_paquete.status_code == 503


# ── E6: rechazar una pendiente y corregir una confirmada ─────────────────────


def test_e6_rechazar_una_pendiente_borra_el_documento_y_permite_volver_a_subirlo(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    extraccion_id = _subir(client, extractor, FACTURA_OLIVOS)

    respuesta = client.post(f"/api/extracciones/{extraccion_id}/rechazo")

    assert respuesta.status_code == 200
    assert respuesta.json()["documento_eliminado"] is True
    assert db.scalar(select(func.count()).select_from(Documento)) == 0
    assert _subir(client, extractor, FACTURA_OLIVOS) is not None  # el mismo archivo entra de nuevo


def test_e6_no_se_rechaza_una_confirmada(client: TestClient, extractor: ExtractorDoble) -> None:
    extraccion_id = _cargar(client, extractor, FACTURA_OLIVOS)

    assert client.post(f"/api/extracciones/{extraccion_id}/rechazo").status_code == 409


def test_e6_corregir_una_confirmada_reemplaza_datos_y_trozo(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    extraccion_id = _cargar(client, extractor, FACTURA_OLIVOS)
    corregida = {**FACTURA_OLIVOS, "total": "120000"}

    respuesta = client.put(f"/api/extracciones/{extraccion_id}/confirmacion", json=corregida)

    assert respuesta.status_code == 200
    assert (respuesta.json()["estado"], respuesta.json()["trozos"]) == ("confirmada", 1)
    assert "120.000 CLP" in _ejecutar(db, "total_facturado", FiltroFacturas()).respuesta
    textos = [t.texto for t in db.scalars(select(Trozo))]
    assert len(textos) == 1 and "120.000 CLP" in textos[0]


def test_e6_corregir_exige_que_este_confirmada_y_valida(
    client: TestClient, extractor: ExtractorDoble
) -> None:
    pendiente = _subir(client, extractor, FACTURA_OLIVOS)
    confirmada = _cargar(client, extractor, {**FACTURA_OLIVOS, "numero": "2"})
    url = "/api/extracciones/{}/confirmacion"

    assert client.put(url.format(pendiente), json=FACTURA_OLIVOS).status_code == 409
    invalida = {**FACTURA_OLIVOS, "fecha": "1203-03-26"}
    assert client.put(url.format(confirmada), json=invalida).status_code == 422


# ── E7: montos acotados ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "total", ["1E+200000", "123.456", "1" * 20], ids=["exponente", "3-dec", "20-dig"]
)
def test_e7_montos_fuera_de_rango_no_validan(total: str) -> None:
    with pytest.raises(ValidationError):
        Factura.model_validate({**FACTURA_OLIVOS, "total": total})


# ── E8: en tests/test_migraciones.py (necesita la base sin la transacción del test) ──


# ── E9: una sola fuente ──────────────────────────────────────────────────────


def test_e9_sin_literales_de_estado_ni_de_decision() -> None:
    patrones = {
        RAIZ / "app/dominio/facturas.py": r"'confirmada'",
        RAIZ / "app/providers/estructurado.py": r"\"(calculo|significado)\"",
        RAIZ / "app/services/enrutamiento.py": r"\"(calculo|significado)\"",
    }
    hallazgos = [
        f"{ruta.name}: {m.group(0)}"
        for ruta, patron in patrones.items()
        for m in re.finditer(patron, ruta.read_text())
    ]

    assert hallazgos == []


def test_e9_la_moneda_no_se_supone() -> None:
    sin_moneda = {clave: valor for clave, valor in FACTURA_OLIVOS.items() if clave != "moneda"}

    with pytest.raises(ValidationError, match="moneda"):
        Factura.model_validate(sin_moneda)


# ── E10: la descripción de origen nombra todos sus valores ──────────────────


def test_e10_la_descripcion_de_origen_nombra_cada_valor() -> None:
    from app.schemas.pregunta import CitaSalida

    descripcion = CitaSalida.model_fields["origen"].description or ""

    assert all(origen.value in descripcion for origen in OrigenTrozo)


# ── E11: casos negativos que faltaban ───────────────────────────────────────


def test_e11_el_calculo_de_una_coleccion_no_ve_la_otra(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    _cargar(client, extractor, FACTURA_OLIVOS, coleccion="otras")

    resultado = _ejecutar(db, "total_facturado", FiltroFacturas())

    assert resultado.documento_ids == []


# ── E12: el filtro de aislamiento no se puede pisar ─────────────────────────


def test_e12_un_argumento_llamado_coleccion_id_no_pisa_el_filtro(db: Session) -> None:
    class ArgumentosTramposos(BaseModel):
        coleccion_id: int = 999999

    espia = HerramientaSQL(
        nombre="espia",
        descripcion="",
        argumentos=ArgumentosTramposos,
        sql=text("SELECT CAST(:coleccion_id AS int) AS c, ARRAY[]::int[] AS documento_ids"),
        formatear=lambda _a, filas: str(filas[0]["c"]),
    )
    destino = catalogo.obtener_coleccion(db, "laboral", "facturas")

    resultado = espia.ejecutar(db, destino.id, "facturas", ArgumentosTramposos())

    assert resultado.respuesta == str(destino.id)


def test_e12_las_herramientas_solo_leen_extracciones_de_su_paquete(
    client: TestClient, db: Session, extractor: ExtractorDoble
) -> None:
    _cargar(client, extractor, FACTURA_OLIVOS)
    otro = _subir(client, extractor, {**FACTURA_OLIVOS, "numero": "X"})
    db.execute(
        update(Extraccion)
        .where(Extraccion.id == otro)
        .values(
            paquete="otro-paquete",
            estado=EstadoExtraccion.CONFIRMADA,
            confirmados={"fecha": "no-es-fecha", "total": "no-es-numero"},
        )
    )
    db.commit()

    resultado = _ejecutar(
        db, "total_facturado", FiltroFacturas()
    )  # sin el filtro, el CAST revienta

    assert "119.000 CLP en 1 factura" in resultado.respuesta


def test_e1_la_cli_retrocea_el_espacio_sin_tocar_las_colecciones_con_paquete(
    client: TestClient, db: Session, extractor: ExtractorDoble, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import nullcontext

    from app.cli import reembeber as cli

    _cargar(client, extractor, FACTURA_OLIVOS)
    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(cli, "obtener_proveedor_embeddings", lambda: proveedor_doble())

    salida = cli.main(["--espacio", "laboral", "--retrocear"])

    origenes = [trozo.origen for trozo in db.scalars(select(Trozo))]
    assert (salida, origenes) == (0, [OrigenTrozo.DATOS])
