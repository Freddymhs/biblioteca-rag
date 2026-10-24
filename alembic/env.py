"""
Alembic environment — runs during migration commands.
Equivalent to having Prisma introspect your schema + manage versions.

Key difference from Prisma: migrations are SQL files you control explicitly.
"""

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure project root is on sys.path so `app` is importable when running
# alembic commands from the project root directory.
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# Load .env so DATABASE_URL and other settings are available without
# having to export them manually before running alembic commands.
load_dotenv(_root / ".env")

# Import all models so Alembic can detect schema changes for autogenerate
from app.config.database import Base  # noqa: E402
import app.models  # noqa: F401 E402 — registers all models on Base.metadata

config = context.config

# Reads logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object used for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url from environment (same pattern as settings.py)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


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
