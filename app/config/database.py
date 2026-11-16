from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.common.logger import logger
from app.config.constantes import ROL_PUBLICO, TIMEOUT_CONSULTA_PUBLICA_MS
from app.config.settings import settings

# Un engine por proceso: administra el pool de conexiones a Postgres.
# I1: `hide_parameters` saca los parámetros de los mensajes de error (allí iría el vector de una
# pregunta) y de los logs.
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, hide_parameters=True)

# Fábrica de sesiones; cada petición HTTP o archivo de la CLI abre la suya.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def crear_engine_publico(url_dueno: str, url_publica: str, permitir_respaldo: bool) -> Engine:
    """Lo público lee con un usuario del grupo `biblioteca_publico`: lo privado lo filtra Postgres
    (RLS), no el código. Toda consulta pública tiene `statement_timeout` (G13).

    Sin `url_publica` (G6): solo si se permite explícitamente (desarrollo), con la conexión del
    dueño y `role=`: la sesión es del dueño, y un `SET ROLE` al dueño la deshace. Si no, la API
    no arranca.
    """
    opciones = f"-c statement_timeout={TIMEOUT_CONSULTA_PUBLICA_MS}"
    if url_publica:
        return create_engine(url_publica, connect_args={"options": opciones}, hide_parameters=True)
    if not permitir_respaldo:
        raise RuntimeError(
            "Falta DATABASE_URL_PUBLICA (usuario del grupo biblioteca_publico, ver "
            "app.cli.usuario_publico). Solo en desarrollo: PERMITIR_PUBLICO_SIN_USUARIO=true"
        )
    logger.warning(
        "Lo público usa la conexión del dueño con role=biblioteca_publico (un SET ROLE al dueño "
        "la deshace): solo para desarrollo. En producción, DATABASE_URL_PUBLICA"
    )
    respaldo = f"-c role={ROL_PUBLICO} {opciones}"
    return create_engine(url_dueno, connect_args={"options": respaldo}, hide_parameters=True)


@lru_cache(maxsize=1)
def obtener_engine_publico() -> Engine:
    """Se crea al primer uso (o al arrancar la API): Alembic y las CLI no lo necesitan."""
    return crear_engine_publico(
        settings.DATABASE_URL,
        settings.DATABASE_URL_PUBLICA.get_secret_value(),
        settings.PERMITIR_PUBLICO_SIN_USUARIO,
    )


def verificar_usuario_publico(engine_publico: Engine) -> None:
    """G7: el usuario con login de lo público no puede ser superusuario, saltarse el RLS ni ser
    el dueño de las tablas, y tiene que ser del grupo. La API se niega a arrancar si no."""
    consulta = text(
        "SELECT r.rolsuper, r.rolbypassrls, pg_has_role(session_user, :grupo, 'MEMBER'), "
        "session_user = (SELECT tableowner FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename = 'trozo') "
        "FROM pg_roles r WHERE r.rolname = session_user"
    )
    with engine_publico.connect() as conexion:
        superusuario, salta_rls, del_grupo, dueno = conexion.execute(
            consulta, {"grupo": ROL_PUBLICO}
        ).one()
    problemas = [
        motivo
        for motivo, presente in (
            ("es superusuario", superusuario),
            ("tiene BYPASSRLS", salta_rls),
            ("es el dueño de las tablas", dueno),
            (f"no es miembro de {ROL_PUBLICO}", not del_grupo),
        )
        if presente
    ]
    if problemas:
        raise RuntimeError(f"El usuario de DATABASE_URL_PUBLICA {', '.join(problemas)}")


class Base(DeclarativeBase):
    """Base de todos los modelos; su `metadata` es lo que compara Alembic."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión por petición, cerrada al terminar.

    Uso en un router: `def ruta(db: Session = Depends(get_db)) -> ...`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_publico() -> Generator[Session, None, None]:
    """Dependencia de la API pública y el MCP: sesión con el rol público (solo lectura, RLS)."""
    db = Session(bind=obtener_engine_publico(), autoflush=False)
    try:
        yield db
    finally:
        db.close()
