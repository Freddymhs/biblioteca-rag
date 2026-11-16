"""trabajo sin cambios

Revision ID: a2eea29f3917
Revises: 1e22705b6540
Create Date: 2026-11-16 08:44:21.107239+00:00

"""
from typing import Sequence, Union

import pgvector.sqlalchemy  # noqa: F401 — autogenerate emite tipos VECTOR sin importarlo
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a2eea29f3917'
down_revision: Union[str, None] = '1e22705b6540'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trabajo', sa.Column('sin_cambios', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('trabajo', 'sin_cambios')
