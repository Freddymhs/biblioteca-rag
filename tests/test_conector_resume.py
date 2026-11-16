"""Conector a la API de resume. El cuerpo de prueba tiene la forma de `GET /api/resume` leída del
código de esa API (`PRODUCTION/fmarcos/fmarcosdev.api.resume`, `resume.service.ts` → `getResume`
devuelve `resume.json` sin envoltorio; `main.ts` pone el prefijo `api`)."""

import json

import httpx
import pytest

from app.conectores.resume import ConectorResume, ErrorConector

BASE = "http://resume.local"
CUERPO_RESUME = {
    "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
    "meta": {"version": "v1.0.0", "lastModified": "2026-11-15"},
    "basics": {
        "name": "Freddy",
        "label": "Backend Developer",
        "summary": "Backend con Node y Python.",
    },
    "work": [
        {
            "name": "SIIGSA, para el SAG",
            "position": "Backend Developer",
            "startDate": "2026-09",
            "endDate": "2026-11",
            "summary": "Sistema de Laboratorio del SAG: 9 microservicios AdonisJS.",
            "technologies": ["AdonisJS", "TypeScript", "SQL Server"],
        }
    ],
    "projects": [
        {"name": "biblioteca-rag", "description": "Motor RAG con cita.", "published": False}
    ],
    "skills": [{"name": "Backend", "keywords": ["Python", "FastAPI"]}],
    "volunteer": [],
}


def _conector(responder) -> tuple[ConectorResume, list[httpx.Request]]:
    pedidos: list[httpx.Request] = []

    def transporte(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return responder(pedido)

    cliente = httpx.Client(transport=httpx.MockTransport(transporte))
    return ConectorResume(BASE, cliente_http=cliente), pedidos


def test_pide_el_resume_completo() -> None:
    conector, pedidos = _conector(lambda _p: httpx.Response(200, json=CUERPO_RESUME))

    conector.registros()

    assert [str(p.url) for p in pedidos] == [f"{BASE}/api/resume"]


def test_un_registro_por_item_de_cada_seccion_con_id_estable() -> None:
    conector, _ = _conector(lambda _p: httpx.Response(200, json=CUERPO_RESUME))

    registros = {registro.id_externo: registro for registro in conector.registros()}

    assert set(registros) == {
        "basics",
        "work:SIIGSA, para el SAG",
        "projects:biblioteca-rag",
        "skills:Backend",
    }  # sin $schema ni meta; una sección vacía no produce registros
    trabajo = registros["work:SIIGSA, para el SAG"]
    assert "Sistema de Laboratorio del SAG" in trabajo.texto
    assert "AdonisJS, TypeScript, SQL Server" in trabajo.texto
    assert trabajo.titulo == "work: SIIGSA, para el SAG"


def test_el_texto_no_depende_del_orden_de_las_claves() -> None:
    """El hash del texto decide si un registro cambió: reordenar claves no es un cambio."""
    reordenado = json.loads(json.dumps(CUERPO_RESUME))
    reordenado["work"][0] = dict(reversed(list(reordenado["work"][0].items())))
    original, _ = _conector(lambda _p: httpx.Response(200, json=CUERPO_RESUME))
    otro, _ = _conector(lambda _p: httpx.Response(200, json=reordenado))

    assert [r.texto for r in original.registros()] == [r.texto for r in otro.registros()]


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(200, text="<html>no es json</html>"),
        httpx.Response(200, json=["no", "es", "objeto"]),
    ],
    ids=["500", "no-json", "no-objeto"],
)
def test_respuestas_invalidas_son_error_del_conector(respuesta: httpx.Response) -> None:
    conector, _ = _conector(lambda _p: respuesta)

    with pytest.raises(ErrorConector):
        conector.registros()


def test_fuente_caida_es_error_del_conector() -> None:
    def caida(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=pedido)

    conector, _ = _conector(caida)

    with pytest.raises(ErrorConector):
        conector.registros()


def test_dos_cargos_en_la_misma_empresa_tienen_ids_distintos() -> None:
    """C2: con solo el nombre, el segundo cargo pisaba al primero y nunca se indexaba."""
    cuerpo = {
        "work": [
            {"name": "INIA", "position": "Analista", "startDate": "2020-01", "summary": "Riego"},
            {"name": "INIA", "position": "Jefe", "startDate": "2023-05", "summary": "Poda"},
        ]
    }
    conector, _ = _conector(lambda _p: httpx.Response(200, json=cuerpo))

    ids = [registro.id_externo for registro in conector.registros()]

    assert len(set(ids)) == 2
    assert all(id_externo.startswith("work:INIA") for id_externo in ids)


def test_elementos_indistinguibles_son_error_del_conector() -> None:
    cuerpo = {"skills": [{"name": "Backend"}, {"name": "Backend"}]}
    conector, _ = _conector(lambda _p: httpx.Response(200, json=cuerpo))

    with pytest.raises(ErrorConector, match="skills:Backend"):
        conector.registros()
