"""servicio publico: flags, rol publico y RLS

Revision ID: 5b7c1e9d4a20
Revises: a256760ec6d6
Create Date: 2026-11-16 12:00:00+00:00

Nombres de roles y tablas escritos a mano: una migración es una foto fija y no importa la app
(los valores vigentes viven en `app/config/constantes.py`: ROL_PUBLICO).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b7c1e9d4a20"
down_revision: Union[str, None] = "a256760ec6d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROL = "biblioteca_publico"
TABLAS_CON_RLS = ("espacio", "coleccion", "documento", "trozo")
# `estructura` (el DoclingDocument: el texto completo), el hash y el id externo no se exponen.
COLUMNAS_PUBLICAS_DOCUMENTO = (
    "id, coleccion_id, nombre_archivo, tipo, paginas, licencia, licencia_verificada, creado_en"
)
# Una política no puede consultar su propia tabla (recursión): la de documento mira la colección,
# y la de trozo, documento + colección.
COLECCION_PUBLICA = "EXISTS (SELECT 1 FROM coleccion c WHERE c.id = {} AND c.publica)"


def upgrade() -> None:
    op.add_column(
        "coleccion", sa.Column("publica", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("documento", sa.Column("licencia", sa.String(length=200), nullable=True))
    op.add_column(
        "documento",
        sa.Column("licencia_verificada", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    # Rol de grupo, sin login. Es de todo el clúster: puede existir de una base anterior.
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROL}') "
        f"THEN CREATE ROLE {ROL} NOLOGIN; END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROL}")
    op.execute(f"GRANT SELECT ON espacio, coleccion, trozo TO {ROL}")
    op.execute(f"GRANT SELECT ({COLUMNAS_PUBLICAS_DOCUMENTO}) ON documento TO {ROL}")
    # Sin GRANT sobre extraccion, trabajo ni alembic_version: el rol no los puede leer.

    # El dueño de las tablas (la app) no queda sujeto a RLS; el rol público solo ve lo público.
    for tabla in TABLAS_CON_RLS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY publico_lee ON coleccion FOR SELECT TO {ROL} USING (publica)")
    op.execute(
        f"CREATE POLICY publico_lee ON espacio FOR SELECT TO {ROL} USING (EXISTS "
        "(SELECT 1 FROM coleccion c WHERE c.espacio_id = espacio.id AND c.publica))"
    )
    op.execute(
        f"CREATE POLICY publico_lee ON documento FOR SELECT TO {ROL} USING (licencia_verificada "
        f"AND {COLECCION_PUBLICA.format('documento.coleccion_id')})"
    )
    op.execute(
        f"CREATE POLICY publico_lee ON trozo FOR SELECT TO {ROL} USING (EXISTS "
        "(SELECT 1 FROM documento d WHERE d.id = trozo.documento_id AND d.licencia_verificada "
        f"AND {COLECCION_PUBLICA.format('d.coleccion_id')}))"
    )

    # Tarea 4.2: `agricultura` es pública (sus documentos siguen ocultos hasta verificar cada
    # licencia, tarea 4.6); `sobre-mi` queda privada por el valor por defecto.
    op.execute(
        "UPDATE coleccion SET publica = true FROM espacio e "
        "WHERE coleccion.espacio_id = e.id AND e.slug = 'laboral' AND coleccion.slug = 'agricultura'"
    )


def downgrade() -> None:
    for tabla in TABLAS_CON_RLS:
        op.execute(f"DROP POLICY IF EXISTS publico_lee ON {tabla}")
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON espacio, coleccion, documento, trozo FROM {ROL}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROL}")
    # El usuario con login (si se creó con `app.cli.usuario_publico`) es miembro: se lo deja, sin grupo.
    op.execute(f"DROP ROLE IF EXISTS {ROL}")
    op.drop_column("documento", "licencia_verificada")
    op.drop_column("documento", "licencia")
    op.drop_column("coleccion", "publica")
