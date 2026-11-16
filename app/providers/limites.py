"""Límite de uso de lo público (tarea 4.4): por IP y, para lo que usa el LLM, tope diario global.

Contadores en Redis con ventana fija desde el primer uso (INCR + EXPIRE NX). Si Redis no
responde, lo público responde 503: sin límite que aplicar, no se sirve (fail-closed).
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from ipaddress import ip_address, ip_network
from threading import BoundedSemaphore

from redis import Redis
from redis.exceptions import RedisError
from starlette.requests import HTTPConnection

from app.common.errors import service_unavailable, too_many_requests
from app.common.logger import logger
from app.config.constantes import (
    ENCABEZADO_IP_CLOUDFLARE,
    PREFIJO_LIMITE,
    VENTANA_DIARIA_SEGUNDOS,
    VENTANA_POR_IP_SEGUNDOS,
    UsoPublico,
)
from app.config.settings import settings

IP_DESCONOCIDA = "desconocida"
VERSION_IPV6 = 6
PREFIJO_IPV6_POR_CLIENTE = 64
MENSAJE_SIN_CUPO = "Hay demasiadas respuestas en curso: vuelve a intentar en unos segundos"
MENSAJE_SIN_LIMITE = (
    "El servicio público no está disponible ahora: vuelve a intentar en unos minutos"
)


class Limitador:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def consumir(self, uso: UsoPublico, ip: str) -> None:
        """Por minuto y por IP: toda petición, antes de validar. 429 al pasarse."""
        por_minuto = {
            UsoPublico.BUSQUEDA: settings.LIMITE_BUSQUEDAS_POR_MINUTO,
            UsoPublico.RESPUESTA: settings.LIMITE_RESPUESTAS_POR_MINUTO,
        }[uso]
        clave = f"{PREFIJO_LIMITE}:{uso}:ip:{clave_ip(ip)}"
        self._contar(clave, por_minuto, VENTANA_POR_IP_SEGUNDOS)

    def reservar_cuota_diaria(self, uso: UsoPublico, ip: str) -> None:
        """Lo caro (embeddings, LLM), recién validada la petición: primero el tope diario de la
        IP, después el global, así una IP pasada de su cuota no gasta la de todos (G2, G3)."""
        por_ip, global_ = {
            UsoPublico.BUSQUEDA: (
                settings.LIMITE_BUSQUEDAS_DIARIAS_POR_IP,
                settings.LIMITE_BUSQUEDAS_DIARIAS,
            ),
            UsoPublico.RESPUESTA: (
                settings.LIMITE_RESPUESTAS_DIARIAS_POR_IP,
                settings.LIMITE_RESPUESTAS_DIARIAS,
            ),
        }[uso]
        hoy = datetime.now(UTC).date().isoformat()
        clave_ip_diaria = f"{PREFIJO_LIMITE}:{uso}:dia:{hoy}:ip:{clave_ip(ip)}"
        self._contar(clave_ip_diaria, por_ip, VENTANA_DIARIA_SEGUNDOS)
        self._contar(f"{PREFIJO_LIMITE}:{uso}:dia:{hoy}", global_, VENTANA_DIARIA_SEGUNDOS)

    def _contar(self, clave: str, maximo: int, ventana_segundos: int) -> None:
        try:
            tuberia = self._redis.pipeline()
            tuberia.incr(clave)
            tuberia.expire(clave, ventana_segundos, nx=True)
            tuberia.ttl(clave)
            usados, _, quedan_segundos = tuberia.execute()
        except RedisError as error:
            # El detalle (host, puerto) va al log: esta respuesta la ve cualquiera.
            logger.error(f"Límite de uso sin Redis: {error!r}")
            raise service_unavailable(MENSAJE_SIN_LIMITE) from error
        if usados > maximo:
            raise too_many_requests(
                f"Límite de {maximo} usos superado; vuelve a intentar en {quedan_segundos} s"
            )


def ip_cliente(conexion: HTTPConnection) -> str:
    """La IP del visitante. El encabezado de Cloudflare solo vale si se configuró el túnel."""
    if settings.CONFIAR_EN_CF_CONNECTING_IP:
        reenviada = conexion.headers.get(ENCABEZADO_IP_CLOUDFLARE)
        if reenviada:
            return reenviada
    return conexion.client.host if conexion.client else IP_DESCONOCIDA


@lru_cache(maxsize=1)
def obtener_limitador() -> Limitador:
    """Dependencia de FastAPI (y del MCP); los tests la reemplazan con un Redis desechable."""
    return Limitador(Redis.from_url(settings.REDIS_URL))


def clave_ip(ip: str) -> str:
    """G3: una IPv6 se agrupa por su /64 (un cliente suele tener la red entera); IPv4 tal cual."""
    try:
        direccion = ip_address(ip)
    except ValueError:
        return ip
    if direccion.version == VERSION_IPV6:
        return str(ip_network(f"{direccion}/{PREFIJO_IPV6_POR_CLIENTE}", strict=False))
    return str(direccion)


class CuposLLM:
    """G4: cuántas respuestas públicas con LLM corren a la vez. Sin cupo, 503 al instante: el
    hilo no queda esperando 120 s al LLM y lo privado y /health siguen teniendo hilos."""

    def __init__(self, cupos: int) -> None:
        self._semaforo = BoundedSemaphore(cupos)

    @contextmanager
    def ocupar(self) -> Generator[None, None, None]:
        if not self._semaforo.acquire(blocking=False):
            raise service_unavailable(MENSAJE_SIN_CUPO)
        try:
            yield
        finally:
            self._semaforo.release()


@lru_cache(maxsize=1)
def obtener_cupos_llm() -> CuposLLM:
    """Uno por proceso; lo comparten la API pública y el MCP."""
    return CuposLLM(settings.MAX_RESPUESTAS_PUBLICAS_SIMULTANEAS)
