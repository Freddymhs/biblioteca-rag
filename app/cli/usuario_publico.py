"""Crea (o actualiza) el usuario con login de la API pública, miembro de `biblioteca_publico`.

    uv run python -m app.cli.usuario_publico

Toma usuario y contraseña de `DATABASE_URL_PUBLICA` (.env) y los aplica con la conexión de dueño
(`DATABASE_URL`). Se corre una vez por base, después de `alembic upgrade head`.
"""

import sys

from psycopg import sql
from sqlalchemy import Connection, Engine, make_url

from app.common.logger import logger
from app.config.constantes import ROL_PUBLICO, TIMEOUT_CONSULTA_PUBLICA_MS
from app.config.database import engine
from app.config.settings import settings

# G7: lo que el usuario de lo público NO puede tener. Al crearlo (y con un dueño SUPERUSER, al
# actualizarlo) se fija todo.
ATRIBUTOS_AL_CREAR = "LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION INHERIT"
# Un dueño CREATEROLE sin SUPERUSER ni CREATEDB (producción) solo puede cambiar, en cada corrida:
# Postgres 16 le niega cualquier ALTER ROLE que nombre SUPERUSER, REPLICATION, BYPASSRLS o CREATEDB,
# aunque sea NO…. Esos no se tocan: `_exigir_usuario_aparte` se niega si el rol los trae.
ATRIBUTOS_AL_ACTUALIZAR = "LOGIN INHERIT"
ATRIBUTOS_PROHIBIDOS = "rolsuper, rolbypassrls, rolreplication, rolcreaterole, rolcreatedb"


def crear_usuario_publico(dueno: Engine, url_publica: str) -> str:
    """Idempotente: crea el usuario o le actualiza contraseña y atributos. Devuelve su nombre.

    Se niega (ValueError) si el usuario es el dueño de las tablas o un rol ya existente con
    SUPERUSER, BYPASSRLS, REPLICATION, CREATEROLE o CREATEDB: no se le quitan privilegios a un rol
    que otro usa para otra cosa (y un dueño sin SUPERUSER no podría quitárselos).
    """
    url = make_url(url_publica)
    if not url.username or not url.password:
        raise ValueError("DATABASE_URL_PUBLICA debe traer usuario y contraseña")
    usuario = sql.Identifier(url.username)
    with dueno.begin() as conexion:
        _exigir_usuario_aparte(conexion, url.username)
        existe = conexion.exec_driver_sql(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (url.username,)
        ).first()
        verbo = "ALTER" if existe else "CREATE"
        puede_fijar_todo = not existe or _es_superusuario(conexion)
        atributos = ATRIBUTOS_AL_CREAR if puede_fijar_todo else ATRIBUTOS_AL_ACTUALIZAR
        cursor = conexion.connection.cursor()
        plantilla = sql.SQL(verbo + " ROLE {} " + atributos + " PASSWORD {}")
        cursor.execute(plantilla.format(usuario, sql.Literal(url.password)))
        cursor.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(ROL_PUBLICO), usuario))
        # G13: además del que pone la conexión, el rol mismo trae su statement_timeout.
        cursor.execute(
            sql.SQL("ALTER ROLE {} SET statement_timeout = {}").format(
                usuario, sql.Literal(TIMEOUT_CONSULTA_PUBLICA_MS)
            )
        )
    return url.username


def _es_superusuario(conexion: Connection) -> bool:
    consulta = "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    return bool(conexion.exec_driver_sql(consulta).scalar_one())


def _exigir_usuario_aparte(conexion: Connection, usuario: str) -> None:
    dueno = conexion.exec_driver_sql(
        "SELECT tableowner FROM pg_tables WHERE schemaname = 'public' AND tablename = 'trozo'"
    ).scalar_one()
    if usuario in (dueno, conexion.exec_driver_sql("SELECT current_user").scalar_one()):
        raise ValueError(f"«{usuario}» es el dueño de las tablas: lo público necesita otro usuario")
    privilegios = conexion.exec_driver_sql(
        f"SELECT {ATRIBUTOS_PROHIBIDOS} FROM pg_roles WHERE rolname = %s", (usuario,)
    ).first()
    if privilegios is None:
        return
    if privilegios.rolsuper or privilegios.rolbypassrls:
        raise ValueError(f"«{usuario}» ya existe con SUPERUSER o BYPASSRLS: elegir otro nombre")
    if any(privilegios) and not _es_superusuario(conexion):
        raise ValueError(
            f"«{usuario}» ya existe con REPLICATION, CREATEROLE o CREATEDB y este dueño no puede "
            "quitárselos: elegir otro nombre"
        )


def main() -> int:
    url_publica = settings.DATABASE_URL_PUBLICA.get_secret_value()
    if not url_publica:
        logger.error("Falta DATABASE_URL_PUBLICA en .env")
        return 1
    try:
        usuario = crear_usuario_publico(engine, url_publica)
    except ValueError as error:
        logger.error(f"No se creó el usuario público: {error}")
        return 1
    logger.info(f"Usuario público «{usuario}» listo (miembro de {ROL_PUBLICO})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
