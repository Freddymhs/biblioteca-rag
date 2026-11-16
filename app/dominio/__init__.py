"""Registro de paquetes de dominio por nombre. Una colección nueva elige uno por data (su campo
`paquete`); un paquete nuevo es un módulo y una entrada aquí."""

from app.common.errors import unprocessable
from app.dominio.base import PaqueteDominio
from app.dominio.facturas import FACTURAS

PAQUETES: dict[str, PaqueteDominio] = {FACTURAS.nombre: FACTURAS}


def obtener_paquete(nombre: str) -> PaqueteDominio:
    paquete = PAQUETES.get(nombre)
    if paquete is None:
        raise unprocessable(
            f"Paquete de dominio desconocido «{nombre}». Disponibles: {sorted(PAQUETES)}"
        )
    return paquete
