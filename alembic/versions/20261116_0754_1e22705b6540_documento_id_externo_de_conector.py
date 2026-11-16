"""documento id externo de conector

Revision ID: 1e22705b6540
Revises: 3dc27ea57217
Create Date: 2026-11-16 07:54:52.416263+00:00

"""
from typing import Sequence, Union

import pgvector.sqlalchemy  # noqa: F401 — autogenerate emite tipos VECTOR sin importarlo
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1e22705b6540'
down_revision: Union[str, None] = '3dc27ea57217'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documento', sa.Column('id_externo', sa.String(length=500), nullable=True))
    op.create_unique_constraint('uq_documento_coleccion_id_externo', 'documento', ['coleccion_id', 'id_externo'])


def downgrade() -> None:
    op.drop_constraint('uq_documento_coleccion_id_externo', 'documento', type_='unique')
    op.drop_column('documento', 'id_externo')
