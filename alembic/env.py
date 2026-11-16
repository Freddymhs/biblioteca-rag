"""
Entorno de Alembic: corre en cada comando de migración (`upgrade`, `revision --autogenerate`).

Toma `DATABASE_URL` de `settings` (entorno, o `.env` sin copiarlo al entorno del proceso) y compara
contra `Base.metadata`, que conoce todos los modelos registrados en `app/models/__init__.py`.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# La raíz del repo en sys.path: `app` se importa aunque alembic corra desde otra carpeta.
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# Imports tardíos intencionales: necesitan la raíz en sys.path, agregada justo arriba.
# No se usa load_dotenv: copiaría el .env completo al entorno del proceso y pisaría la
# configuración de quien importe esto (los tests corren alembic dentro de su proceso).
import app.models  # noqa: F401 E402 — registra todos los modelos en Base.metadata
from app.config.database import Base  # noqa: E402
from app.config.settings import settings  # noqa: E402

config = context.config

# Reads logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object used for 'autogenerate' support
target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL script without DB connection.
    Useful for reviewing what will change before applying.

    Usage: alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the real DB and applies changes.

    Usage: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
