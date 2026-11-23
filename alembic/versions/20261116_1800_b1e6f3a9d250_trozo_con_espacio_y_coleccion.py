"""trozo con espacio_id y coleccion_id desnormalizados (FASE_6, 6.3)

Revision ID: b1e6f3a9d250
Revises: 9c4d2e7f1a36
Create Date: 2026-11-16 18:00:00+00:00

Filtrar por espacio y colección sin JOIN: los btree de `trozo` acotan qué trozos entran a la
búsqueda exacta de `buscar` y dejan listo un índice HNSW parcial por espacio si algún día hace
falta. Que el filtro esté en la misma tabla NO corrige el recorrido HNSW (medido, con y sin
`iterative_scan`: `DECISION_HNSW_FILTROS.md`). Los completa un trigger desde el documento: ningún
INSERT puede olvidarlos ni contradecirlos.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1e6f3a9d250'
down_revision: Union[str, None] = '9c4d2e7f1a36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FUNCION = "trozo_completar_ubicacion"


def upgrade() -> None:
    op.add_column('trozo', sa.Column('espacio_id', sa.Integer(), nullable=True))
    op.add_column('trozo', sa.Column('coleccion_id', sa.Integer(), nullable=True))
    # Lo que ya hubiera (hoy no hay datos en producción; la base de desarrollo sí tiene).
    op.execute(
        "UPDATE trozo t SET coleccion_id = d.coleccion_id, espacio_id = c.espacio_id "
        "FROM documento d JOIN coleccion c ON c.id = d.coleccion_id WHERE d.id = t.documento_id"
    )
    op.alter_column('trozo', 'espacio_id', nullable=False)
    op.alter_column('trozo', 'coleccion_id', nullable=False)
    op.create_foreign_key('trozo_espacio_id_fkey', 'trozo', 'espacio', ['espacio_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('trozo_coleccion_id_fkey', 'trozo', 'coleccion', ['coleccion_id'], ['id'], ondelete='RESTRICT')
    op.create_index(op.f('ix_trozo_espacio_id'), 'trozo', ['espacio_id'], unique=False)
    op.create_index(op.f('ix_trozo_coleccion_id'), 'trozo', ['coleccion_id'], unique=False)
    op.execute(f"""
        CREATE FUNCTION {FUNCION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT d.coleccion_id, c.espacio_id INTO NEW.coleccion_id, NEW.espacio_id
            FROM documento d JOIN coleccion c ON c.id = d.coleccion_id
            WHERE d.id = NEW.documento_id;
            RETURN NEW;
        END $$
    """)
    op.execute(
        f"CREATE TRIGGER {FUNCION} BEFORE INSERT OR UPDATE OF documento_id ON trozo "
        f"FOR EACH ROW EXECUTE FUNCTION {FUNCION}()"
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {FUNCION} ON trozo")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCION}()")
    op.drop_index(op.f('ix_trozo_coleccion_id'), table_name='trozo')
    op.drop_index(op.f('ix_trozo_espacio_id'), table_name='trozo')
    op.drop_constraint('trozo_coleccion_id_fkey', 'trozo', type_='foreignkey')
    op.drop_constraint('trozo_espacio_id_fkey', 'trozo', type_='foreignkey')
    op.drop_column('trozo', 'coleccion_id')
    op.drop_column('trozo', 'espacio_id')
