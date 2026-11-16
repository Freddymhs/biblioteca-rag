"""Contrato de un conector: una fuente externa que entrega registros de texto con id estable."""

from dataclasses import dataclass
from typing import Protocol

from app.common.errors import ErrorProveedor


class ErrorConector(ErrorProveedor):
    """La fuente no respondió o respondió algo que no es lo documentado: 502."""


@dataclass(frozen=True)
class Registro:
    # Estable entre sincronizaciones: decide si un registro es nuevo, cambió o desapareció.
    id_externo: str
    titulo: str  # lo que la cita muestra como «documento»
    texto: str


class Conector(Protocol):
    nombre: str

    def registros(self) -> list[Registro]: ...
