"""Cola de trabajos (Redis + arq). La conexión se abre al primer uso: la API arranca sin Redis
y solo los endpoints que encolan responden 503 si no está."""

from functools import lru_cache
from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from redis.exceptions import RedisError

from app.common.errors import service_unavailable
from app.config.settings import settings


class ColaArq:
    def __init__(self, redis_url: str) -> None:
        self._ajustes = RedisSettings.from_dsn(redis_url)
        self._pool: ArqRedis | None = None  # se crea al primer encolado

    async def verificar(self) -> None:
        """Se llama antes de crear un trabajo: si Redis no responde, no se crea nada."""
        try:
            pool = await self._conectar()
            await pool.ping()
        except (RedisError, OSError) as error:
            raise service_unavailable(
                f"La cola de trabajos (Redis) no responde: {error}"
            ) from error

    # `Any`: argumentos de la función del worker, que arq serializa tal cual.
    async def encolar(self, funcion: str, *argumentos: Any, id_tarea: str) -> None:
        """`id_tarea` determinista: el barrido de huérfanos consulta su estado en Redis."""
        try:
            pool = await self._conectar()
            await pool.enqueue_job(funcion, *argumentos, _job_id=id_tarea)
        except (RedisError, OSError) as error:
            raise service_unavailable(
                f"La cola de trabajos (Redis) no responde: {error}"
            ) from error

    async def _conectar(self) -> ArqRedis:
        pool = self._pool or await create_pool(self._ajustes)
        self._pool = pool
        return pool


@lru_cache(maxsize=1)
def obtener_cola() -> ColaArq:
    """Dependencia de FastAPI; los tests la reemplazan con un doble."""
    return ColaArq(settings.REDIS_URL)
