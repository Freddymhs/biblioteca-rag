"""defensa en profundidad de lo publico (auditoria FASE_4, G13)

Revision ID: 7e3a9c2b5d14
Revises: 5b7c1e9d4a20
Create Date: 2026-11-16 15:00:00+00:00

- RLS sin políticas en `extraccion` y `trabajo`: hoy el rol público no tiene permiso sobre ellas;
  si alguien se lo concediera por error, igual no vería ninguna fila.
- Una colección con paquete (datos de facturas, etc.) no puede ser pública: lo impide la base.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e3a9c2b5d14'
down_revision: Union[str, None] = '5b7c1e9d4a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLAS_SIN_POLITICA = ("extraccion", "trabajo")


def upgrade() -> None:
    for tabla in TABLAS_SIN_POLITICA:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.create_check_constraint(
        "ck_coleccion_paquete_no_publica", "coleccion", "NOT (publica AND paquete IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_constraint("ck_coleccion_paquete_no_publica", "coleccion", type_="check")
    for tabla in TABLAS_SIN_POLITICA:
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
