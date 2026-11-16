"""Qué ruta es privada y cuál pública: un solo criterio para el middleware de la clave y para el
manejo de errores (lo público nunca muestra detalles internos)."""

from app.config.constantes import PREFIJO_API, PREFIJO_PUBLICO, RUTA_MCP


def es_ruta_publica(ruta: str) -> bool:
    return ruta.startswith((PREFIJO_PUBLICO, RUTA_MCP))


def es_ruta_privada(ruta: str) -> bool:
    """Todo `/api` salvo `/api/publico`. Lo mismo que agrupa `main.py` con la dependencia."""
    return ruta.startswith(PREFIJO_API) and not es_ruta_publica(ruta)
