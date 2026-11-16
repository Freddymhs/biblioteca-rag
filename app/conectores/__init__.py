"""Registro de conectores por nombre. Agregar uno = una entrada aquí y su módulo."""

from collections.abc import Callable

from app.common.errors import service_unavailable, unprocessable
from app.conectores.base import Conector
from app.conectores.resume import NOMBRE as RESUME
from app.conectores.resume import ConectorResume
from app.config.settings import Settings


def _resume(config: Settings) -> Conector:
    if not config.RESUME_API_URL:
        raise service_unavailable("Conector «resume» sin configurar: falta RESUME_API_URL en .env")
    return ConectorResume(config.RESUME_API_URL)


FABRICAS: dict[str, Callable[[Settings], Conector]] = {RESUME: _resume}


def crear_conector(nombre: str, config: Settings) -> Conector:
    fabrica = FABRICAS.get(nombre)
    if fabrica is None:
        raise unprocessable(f"Conector desconocido «{nombre}». Disponibles: {sorted(FABRICAS)}")
    return fabrica(config)
