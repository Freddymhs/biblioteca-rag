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
