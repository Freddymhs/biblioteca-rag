"""documento estructura docling

Revision ID: 8d1f2a9c7b31
Revises: 3467fd377bbf
Create Date: 2026-11-16 07:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d1f2a9c7b31"
down_revision: str | None = "3467fd377bbf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: los documentos ingeridos antes no tienen estructura guardada; el re-embed los
    # puede re-vectorizar desde sus trozos, pero no re-trocear.
    op.add_column(
        "documento",
        sa.Column("estructura", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documento", "estructura")
