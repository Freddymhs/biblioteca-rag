"""Contrato de un paquete de dominio (FASE_3).

Un paquete define, para un tipo de documento: el esquema Pydantic de sus datos, cómo se escriben
como texto para embeber una vez confirmados, y sus herramientas SQL FIJAS. El LLM nunca escribe
SQL: elige una herramienta y le pasa argumentos que valida el modelo Pydantic de esa herramienta.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import TextClause
from sqlalchemy.orm import Session

from app.config.constantes import EstadoExtraccion

# `Any`: una fila del SQL de la herramienta (montos, fechas, conteos) que su formateador lee.
FilaCalculo = dict[str, Any]


@dataclass(frozen=True)
class ResultadoCalculo:
    respuesta: str
    documento_ids: list[int]


@dataclass(frozen=True)
class HerramientaSQL:
    nombre: str
    descripcion: str  # lo que el clasificador lee para elegirla
    argumentos: type[BaseModel]  # valida lo que propone el LLM: nada sin validar llega al SQL
    # Texto fijo con parámetros; filtra por :coleccion_id, :paquete y :estado_confirmada, y devuelve
    # una columna `documento_ids` (int[]) con los documentos que respaldan cada fila (la cita).
    sql: TextClause
    formatear: Callable[[BaseModel, Sequence[FilaCalculo]], str]

    def ejecutar(
        self, db: Session, coleccion_id: int, paquete: str, argumentos: BaseModel
    ) -> ResultadoCalculo:
        # Los filtros de aislamiento van AL FINAL: ningún argumento (ni uno futuro con el mismo
        # nombre) puede pisar la colección, el paquete ni el estado.
        parametros = {
            **argumentos.model_dump(),
            "coleccion_id": coleccion_id,
            "paquete": paquete,
            "estado_confirmada": EstadoExtraccion.CONFIRMADA.value,
        }
        filas = [dict(fila) for fila in db.execute(self.sql, parametros).mappings()]
        documentos = sorted({i for fila in filas for i in (fila["documento_ids"] or [])})
        return ResultadoCalculo(self.formatear(argumentos, filas), documentos)


@dataclass(frozen=True)
class PaqueteDominio:
    nombre: str
    descripcion: str
    esquema: type[BaseModel]  # datos de UN documento; su JSON Schema es el formulario
    texto_para_embeber: Callable[[BaseModel], str]  # lo único que se embebe: lo confirmado
    herramientas: tuple[HerramientaSQL, ...]

    def herramienta(self, nombre: str) -> HerramientaSQL | None:
        return next((h for h in self.herramientas if h.nombre == nombre), None)
