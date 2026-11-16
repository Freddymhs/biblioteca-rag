"""paquetes de dominio y extracciones

Revision ID: a256760ec6d6
Revises: a2eea29f3917
Create Date: 2026-11-16 09:26:59.484032+00:00

"""
from typing import Sequence, Union

import pgvector.sqlalchemy  # noqa: F401 — autogenerate emite tipos VECTOR sin importarlo
import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a256760ec6d6'
down_revision: Union[str, None] = 'a2eea29f3917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Valor nuevo del enum de origen: trozos que vienen de datos confirmados por una persona.
    op.execute("ALTER TYPE origen_trozo ADD VALUE IF NOT EXISTS 'datos'")
    op.create_table('extraccion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('documento_id', sa.Integer(), nullable=False),
    sa.Column('paquete', sa.String(length=64), nullable=False),
    sa.Column('estado', sa.Enum('pendiente', 'confirmada', name='estado_extraccion'), nullable=False),
    sa.Column('propuesta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('errores', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confirmados', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('confirmado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['documento_id'], ['documento.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('documento_id')
    )
    op.add_column('coleccion', sa.Column('paquete', sa.String(length=64), nullable=True))


def downgrade() -> None:
    # Antes de quitar la tabla: los trozos de datos confirmados no los sabe leer el código anterior.
    op.execute("DELETE FROM trozo WHERE origen = 'datos'")
    op.drop_column('coleccion', 'paquete')
    op.drop_table('extraccion')
    sa.Enum(name="estado_extraccion").drop(op.get_bind(), checkfirst=True)
    # Postgres no permite quitar un valor de un enum: 'datos' queda en origen_trozo (inofensivo).
