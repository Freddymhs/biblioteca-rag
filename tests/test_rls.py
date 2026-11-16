"""Tarea 4.1: el rol público no ve lo privado, ni siquiera con SQL directo (Postgres real, RLS).

Los datos se escriben y confirman de verdad (otra conexión no ve una transacción abierta) y se
borran al final. El usuario con login se crea con la misma función que usa la CLI.
"""

import secrets
from collections.abc import Generator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.cli.usuario_publico import crear_usuario_publico
from app.config.constantes import DIMENSION_EMBEDDING, ROL_PUBLICO

USUARIO = "rls_web_test"
VECTOR = "[" + ",".join(["0.1"] * DIMENSION_EMBEDDING) + "]"
# (espacio, colección, pública, licencia verificada) → un documento con un trozo cada una.
CASOS = (
    ("rls-pub", "abierta", True, True),
    ("rls-pub", "sin-licencia", True, False),
    ("rls-priv", "sobre-mi", False, True),
)


def _sembrar(conexion: Connection) -> None:
    for espacio in {caso[0] for caso in CASOS}:
        conexion.execute(text("INSERT INTO espacio (slug, nombre) VALUES (:s, :s)"), {"s": espacio})
    for espacio, coleccion, publica, verificada in CASOS:
        coleccion_id = conexion.execute(
            text(
                "INSERT INTO coleccion (espacio_id, slug, nombre, publica) "
                "SELECT id, :c, :c, :p FROM espacio WHERE slug = :e RETURNING id"
            ),
            {"e": espacio, "c": coleccion, "p": publica},
        ).scalar_one()
        documento_id = conexion.execute(
            text(
                "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo, "
                "licencia_verificada, estructura) VALUES (:c, :n, :h, 'txt', :v, '{}') RETURNING id"
            ),
            {
                "c": coleccion_id,
                "n": f"{coleccion}.txt",
                "h": coleccion.ljust(64, "0"),
                "v": verificada,
            },
        ).scalar_one()
        conexion.execute(
            text(
                "INSERT INTO trozo (documento_id, orden, texto, embedding, embedding_model) "
                "VALUES (:d, 0, :t, :v, 'm')"
            ),
            {"d": documento_id, "t": f"texto de {coleccion}", "v": VECTOR},
        )


def _limpiar(conexion: Connection) -> None:
    espacios = {"s": [caso[0] for caso in CASOS]}
    filtro = (
        "SELECT c.id FROM coleccion c JOIN espacio e ON e.id = c.espacio_id WHERE e.slug = ANY(:s)"
    )
    conexion.execute(text(f"DELETE FROM documento WHERE coleccion_id IN ({filtro})"), espacios)
    conexion.execute(text(f"DELETE FROM coleccion WHERE id IN ({filtro})"), espacios)
    conexion.execute(text("DELETE FROM espacio WHERE slug = ANY(:s)"), espacios)


@pytest.fixture(scope="module")
def publico(engine: Engine) -> Generator[Engine, None, None]:
    """Conexión como un usuario con login miembro del grupo público, igual que en producción."""
    with engine.begin() as conexion:
        _sembrar(conexion)
    url = engine.url.set(username=USUARIO, password=secrets.token_urlsafe(16))
    crear_usuario_publico(engine, url.render_as_string(hide_password=False))
    engine_publico = create_engine(url)
    try:
        yield engine_publico
    finally:
        engine_publico.dispose()
        with engine.begin() as conexion:
            _limpiar(conexion)
            conexion.execute(text(f"DROP ROLE IF EXISTS {USUARIO}"))


def _leer(engine_publico: Engine, sql: str) -> list[str]:
    with engine_publico.connect() as conexion:
        return [fila[0] for fila in conexion.execute(text(sql))]


def test_el_rol_publico_solo_ve_colecciones_publicas(publico: Engine) -> None:
    colecciones = _leer(publico, "SELECT slug FROM coleccion ORDER BY slug")
    espacios = _leer(publico, "SELECT slug FROM espacio")

    assert colecciones == ["abierta", "sin-licencia"]
    assert espacios == ["rls-pub"]  # el espacio privado tampoco aparece


def test_un_trozo_es_publico_solo_con_coleccion_publica_y_licencia_verificada(
    publico: Engine,
) -> None:
    textos = _leer(publico, "SELECT texto FROM trozo")
    documentos = _leer(publico, "SELECT nombre_archivo FROM documento")

    assert (textos, documentos) == (["texto de abierta"], ["abierta.txt"])


def test_buscar_la_privada_por_nombre_no_devuelve_nada(publico: Engine) -> None:
    filas = _leer(
        publico,
        "SELECT t.texto FROM trozo t JOIN documento d ON d.id = t.documento_id "
        "JOIN coleccion c ON c.id = d.coleccion_id WHERE c.slug = 'sobre-mi'",
    )

    assert filas == []


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT estructura FROM documento",  # el texto completo de Docling: columna no otorgada
        "SELECT hash_contenido FROM documento",
        "SELECT id_externo FROM documento",
        "SELECT * FROM documento",
        "SELECT count(*) FROM extraccion",
        "SELECT count(*) FROM trabajo",
        "UPDATE coleccion SET publica = true",
        "INSERT INTO espacio (slug, nombre) VALUES ('x', 'x')",
        "DELETE FROM trozo",
        f"SET ROLE {ROL_PUBLICO}; RESET ROLE; SELECT count(*) FROM extraccion",  # no escapa
        "SET ROLE test",
    ],
    ids=[
        "estructura",
        "hash",
        "id-externo",
        "documento-entero",
        "extraccion",
        "trabajo",
        "update",
        "insert",
        "delete",
        "reset",
        "rol-dueno",
    ],
)
def test_el_rol_publico_no_escribe_ni_escala(publico: Engine, sql: str) -> None:
    with publico.connect() as conexion, pytest.raises(DBAPIError, match="permission denied"):
        conexion.exec_driver_sql(sql)


def test_el_dueno_sigue_viendo_todo(engine: Engine, publico: Engine) -> None:
    with engine.connect() as conexion:
        colecciones = conexion.execute(
            text(
                "SELECT count(*) FROM coleccion "
                "WHERE slug IN ('abierta', 'sin-licencia', 'sobre-mi')"
            )
        ).scalar_one()

    assert colecciones == len(CASOS)
