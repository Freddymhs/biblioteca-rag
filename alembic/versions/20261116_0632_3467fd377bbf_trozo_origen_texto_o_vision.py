"""trozo origen texto o vision

Revision ID: 3467fd377bbf
Revises: 4c0ae2807286
Create Date: 2026-11-16 06:32:45.069052+00:00

"""
from typing import Sequence, Union

import pgvector.sqlalchemy  # noqa: F401 — autogenerate emite tipos VECTOR sin importarlo
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3467fd377bbf'
down_revision: Union[str, None] = '4c0ae2807286'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORIGEN_TROZO = sa.Enum("texto", "vision", name="origen_trozo")


def upgrade() -> None:
    # add_column, a diferencia de create_table, no crea el tipo enum en Postgres.
    ORIGEN_TROZO.create(op.get_bind(), checkfirst=True)
    # Los trozos que ya existen vienen todos de Docling: el default los marca como «texto».
    op.add_column(
        "trozo", sa.Column("origen", ORIGEN_TROZO, server_default="texto", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("trozo", "origen")
    ORIGEN_TROZO.drop(op.get_bind(), checkfirst=True)
