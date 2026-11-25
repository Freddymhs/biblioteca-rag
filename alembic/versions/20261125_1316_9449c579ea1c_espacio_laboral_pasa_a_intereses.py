"""El espacio «laboral» pasa a llamarse «intereses»

Revision ID: 9449c579ea1c
Revises: c7a2d4e8f613
Create Date: 2026-11-25 16:16:46+00:00

Deja en el código el `UPDATE` que se aplicó a mano en producción el 2026-11-25: la API no tiene ruta
para renombrar un espacio. Es idempotente: en una base donde ya se llama «intereses», o donde «laboral»
no existe (una base nueva y vacía), no hace nada; y no pisa un «intereses» existente (el slug es único).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9449c579ea1c'
down_revision: Union[str, None] = 'c7a2d4e8f613'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copiados y no importados: una migración no cambia si mañana cambian las constantes.
SLUG_ANTERIOR = "laboral"
NOMBRE_ANTERIOR = "Laboral"
SLUG_NUEVO = "intereses"
NOMBRE_NUEVO = "Intereses"

# `:destino` es el slug al que pasa; `:origen`, el que tiene hoy. No pisa un destino ya existente.
RENOMBRAR_ESPACIO = sa.text(
    "UPDATE espacio SET slug = :destino, nombre = :nombre_destino "
    "WHERE slug = :origen AND NOT EXISTS (SELECT 1 FROM espacio WHERE slug = :destino)"
)


def upgrade() -> None:
    op.execute(
        RENOMBRAR_ESPACIO.bindparams(origen=SLUG_ANTERIOR, destino=SLUG_NUEVO, nombre_destino=NOMBRE_NUEVO)
    )


def downgrade() -> None:
    op.execute(
        RENOMBRAR_ESPACIO.bindparams(origen=SLUG_NUEVO, destino=SLUG_ANTERIOR, nombre_destino=NOMBRE_ANTERIOR)
    )
