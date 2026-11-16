"""trabajos de ingesta

Revision ID: 3dc27ea57217
Revises: 8d1f2a9c7b31
Create Date: 2026-11-16 07:40:52.748290+00:00

"""
from typing import Sequence, Union

import pgvector.sqlalchemy  # noqa: F401 — autogenerate emite tipos VECTOR sin importarlo
import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3dc27ea57217'
down_revision: Union[str, None] = '8d1f2a9c7b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('trabajo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('coleccion_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('lote', 'sincronizacion', name='tipo_trabajo'), nullable=False),
    sa.Column('total', sa.Integer(), nullable=True),
    sa.Column('ingeridos', sa.Integer(), server_default='0', nullable=False),
    sa.Column('duplicados', sa.Integer(), server_default='0', nullable=False),
    sa.Column('rechazados', sa.Integer(), server_default='0', nullable=False),
    sa.Column('errores', sa.Integer(), server_default='0', nullable=False),
    sa.Column('eliminados', sa.Integer(), server_default='0', nullable=False),
    sa.Column('trozos', sa.Integer(), server_default='0', nullable=False),
    sa.Column('ultimo_error', sa.Text(), nullable=True),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['coleccion_id'], ['coleccion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trabajo_coleccion_id'), 'trabajo', ['coleccion_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trabajo_coleccion_id'), table_name='trabajo')
    op.drop_table('trabajo')
    # drop_table no borra el tipo enum de Postgres; sin esto, upgrade tras downgrade falla.
    sa.Enum(name="tipo_trabajo").drop(op.get_bind(), checkfirst=True)
