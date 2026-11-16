import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.config.database import Base


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
    with engine.connect() as connection, pytest.raises(IntegrityError, match="ck_trozo_rango"):
        connection.execute(
            text(
                "INSERT INTO trozo (documento_id, orden, texto, pagina_inicio, pagina_fin, "
                "embedding, embedding_model) VALUES (1, 0, 'x', 5, 4, :v, 'm')"
            ),
            {"v": "[" + ",".join(["0"] * 1024) + "]"},
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
        command.downgrade(config, "-1")
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
