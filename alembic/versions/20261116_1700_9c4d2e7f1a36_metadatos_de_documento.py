"""metadatos de documento: titulo, fuente, anno (FASE_6, 6.1)

Revision ID: 9c4d2e7f1a36
Revises: 7e3a9c2b5d14
Create Date: 2026-11-16 17:00:00+00:00

El rol público lee `documento` por columnas concedidas una a una (FASE_4): sin el GRANT de
abajo, la búsqueda pública fallaría al pedir el título.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9c4d2e7f1a36'
down_revision: Union[str, None] = '7e3a9c2b5d14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROL = "biblioteca_publico"


def upgrade() -> None:
    op.add_column('documento', sa.Column('titulo', sa.String(length=500), nullable=True))
    op.add_column('documento', sa.Column('fuente', sa.String(length=300), nullable=True))
    op.add_column('documento', sa.Column('anno', sa.Integer(), nullable=True))
    op.create_check_constraint("ck_documento_anno", "documento", "anno BETWEEN 1000 AND 2100")
    op.execute(f"GRANT SELECT (titulo, fuente, anno) ON documento TO {ROL}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT (titulo, fuente, anno) ON documento FROM {ROL}")
    op.drop_constraint("ck_documento_anno", "documento", type_="check")
    op.drop_column('documento', 'anno')
    op.drop_column('documento', 'fuente')
    op.drop_column('documento', 'titulo')
