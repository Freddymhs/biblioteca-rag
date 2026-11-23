import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.config.database import Base

# La revisión anterior a `a256760ec6d6` (paquetes): destino explícito, no «-1».
ANTES_DE_PAQUETES = "a2eea29f3917"
# La anterior a la que unifica el identificador de bge-m3 (6.8, B2).
ANTES_DE_BGE_M3_COMPARTIDO = "b1e6f3a9d250"


def test_modelos_y_migraciones_coinciden(engine: Engine) -> None:
    """Si un modelo cambia sin su migración, autogenerate encontraría diferencias."""
    with engine.connect() as connection:
        diferencias = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diferencias == []


def test_downgrade_y_upgrade_ida_y_vuelta(engine: Engine) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "base")
    with engine.connect() as connection:
        tablas_tras_downgrade = connection.execute(
            text("SELECT count(*) FROM pg_tables WHERE tablename = 'trozo'")
        ).scalar_one()
    command.upgrade(config, "head")

    assert tablas_tras_downgrade == 0


def test_indice_hnsw_por_coseno(engine: Engine) -> None:
    with engine.connect() as connection:
        definicion = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_trozo_embedding_hnsw'")
        ).scalar_one()

    assert "USING hnsw" in definicion
    assert "vector_cosine_ops" in definicion


def test_rango_de_paginas_invertido_se_rechaza(engine: Engine) -> None:
    """Con un documento real (el trigger de 6.3 completa espacio y colección desde él); nada se
    confirma: la conexión se cierra sin commit."""
    with engine.connect() as connection:
        documento = connection.execute(
            text(
                "WITH e AS (INSERT INTO espacio (slug, nombre) VALUES ('rango', 'r') "
                "RETURNING id), "
                "c AS (INSERT INTO coleccion (espacio_id, slug, nombre) "
                "SELECT id, 'r', 'r' FROM e RETURNING id) "
                "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo) "
                "SELECT id, 'r.txt', repeat('r', 64), 'txt' FROM c RETURNING id"
            )
        ).scalar_one()
        with pytest.raises(IntegrityError, match="ck_trozo_rango"):
            connection.execute(
                text(
                    "INSERT INTO trozo (documento_id, orden, texto, pagina_inicio, pagina_fin, "
                    "embedding, embedding_model) VALUES (:d, 0, 'x', 5, 4, :v, 'm')"
                ),
                {"d": documento, "v": "[" + ",".join(["0"] * 1024) + "]"},
            )


def test_e8_el_downgrade_de_paquetes_borra_los_trozos_de_datos(engine: Engine) -> None:
    """Auditoría FASE_3 E8: sin esto quedaban trozos `datos` que el código anterior no sabe leer."""
    config = Config("alembic.ini")
    with (
        engine.begin() as conexion
    ):  # datos confirmados de verdad, fuera de toda transacción de test
        espacio = conexion.execute(
            text("INSERT INTO espacio (slug, nombre) VALUES ('e8', 'e8') RETURNING id")
        ).scalar_one()
        coleccion = conexion.execute(
            text(
                "INSERT INTO coleccion (espacio_id, slug, nombre, paquete) "
                "VALUES (:e, 'e8', 'e8', 'facturas') RETURNING id"
            ),
            {"e": espacio},
        ).scalar_one()
        documento = conexion.execute(
            text(
                "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo) "
                "VALUES (:c, 'f.txt', :h, 'txt') RETURNING id"
            ),
            {"c": coleccion, "h": "e8".ljust(64, "0")},
        ).scalar_one()
        conexion.execute(
            text(
                "INSERT INTO trozo "
                "(documento_id, orden, texto, embedding, embedding_model, origen) "
                "VALUES (:d, 0, 'datos', :v, 'm', 'datos')"
            ),
            {"d": documento, "v": "[" + ",".join(["0"] * 1024) + "]"},
        )
    try:
        command.downgrade(config, ANTES_DE_PAQUETES)
        with engine.connect() as conexion:
            quedan = conexion.execute(
                text("SELECT count(*) FROM trozo WHERE origen::text = 'datos'")
            ).scalar_one()
    finally:
        command.upgrade(config, "head")
        with engine.begin() as conexion:
            conexion.execute(
                text(
                    "DELETE FROM documento WHERE nombre_archivo = 'f.txt' AND hash_contenido = :h"
                ),
                {"h": "e8".ljust(64, "0")},
            )
            conexion.execute(text("DELETE FROM coleccion WHERE slug = 'e8'"))
            conexion.execute(text("DELETE FROM espacio WHERE slug = 'e8'"))

    assert quedan == 0


def test_b2_los_trozos_de_bge_m3_de_cualquier_proveedor_quedan_con_un_identificador(
    engine: Engine,
) -> None:
    """6.8: Ollama y Cloudflare dan el mismo vector (coseno 0,99999); lo ya embebido con
    cualquiera de los dos queda con el identificador común y no hay que re-embeber."""
    config = Config("alembic.ini")
    vector = "[" + ",".join(["0"] * 1024) + "]"
    command.downgrade(config, ANTES_DE_BGE_M3_COMPARTIDO)
    try:
        with engine.begin() as conexion:
            documento = conexion.execute(
                text(
                    "WITH e AS (INSERT INTO espacio (slug, nombre) VALUES ('b2', 'b2') "
                    "RETURNING id), "
                    "c AS (INSERT INTO coleccion (espacio_id, slug, nombre) "
                    "SELECT id, 'b2', 'b2' FROM e RETURNING id) "
                    "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo) "
                    "SELECT id, 'b2.txt', repeat('b', 64), 'txt' FROM c RETURNING id"
                )
            ).scalar_one()
            for orden, modelo in enumerate(
                ["ollama:bge-m3", "cloudflare:@cf/baai/bge-m3", "ollama:nomic"]
            ):
                conexion.execute(
                    text(
                        "INSERT INTO trozo (documento_id, orden, texto, embedding, "
                        "embedding_model) VALUES (:d, :o, 'x', :v, :m)"
                    ),
                    {"d": documento, "o": orden, "v": vector, "m": modelo},
                )
        command.upgrade(config, "head")
        with engine.connect() as conexion:
            modelos = (
                conexion.execute(
                    text(
                        "SELECT t.embedding_model FROM trozo t JOIN documento d "
                        "ON d.id = t.documento_id WHERE d.nombre_archivo = 'b2.txt' "
                        "ORDER BY t.orden"
                    )
                )
                .scalars()
                .all()
            )
    finally:
        command.upgrade(config, "head")
        with engine.begin() as conexion:
            conexion.execute(text("DELETE FROM documento WHERE nombre_archivo = 'b2.txt'"))
            conexion.execute(text("DELETE FROM coleccion WHERE slug = 'b2'"))
            conexion.execute(text("DELETE FROM espacio WHERE slug = 'b2'"))

    assert modelos == ["bge-m3", "bge-m3", "ollama:nomic"]
