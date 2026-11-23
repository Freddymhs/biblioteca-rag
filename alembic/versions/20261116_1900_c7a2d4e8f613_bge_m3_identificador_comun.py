"""bge-m3 con un identificador común para Ollama y Cloudflare (FASE_6, 6.8, auditoría B2)

Revision ID: c7a2d4e8f613
Revises: b1e6f3a9d250
Create Date: 2026-11-16 19:00:00+00:00

Medido con `scripts/benchmark.py`: el mismo texto da el mismo vector en los dos proveedores (coseno
mínimo 0,999991; textos distintos, 0,46 como máximo). Lo ya embebido con cualquiera de los dos pasa
al identificador de `MODELOS_EQUIVALENTES` (`app/config/constantes.py`).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7a2d4e8f613'
down_revision: Union[str, None] = 'b1e6f3a9d250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copiados y no importados: una migración no cambia si mañana cambian las constantes.
COMUN = "bge-m3"
ANTERIORES = ("ollama:bge-m3", "cloudflare:@cf/baai/bge-m3")
# Al bajar no se sabe con qué proveedor se embebió: se elige el de desarrollo.
AL_BAJAR = "ollama:bge-m3"


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE trozo SET embedding_model = :comun WHERE embedding_model IN :anteriores")
        .bindparams(sa.bindparam("anteriores", expanding=True))
        .bindparams(comun=COMUN, anteriores=list(ANTERIORES))
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE trozo SET embedding_model = :al_bajar WHERE embedding_model = :comun")
        .bindparams(al_bajar=AL_BAJAR, comun=COMUN)
    )
