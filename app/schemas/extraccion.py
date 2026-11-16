from typing import Any

from pydantic import BaseModel, Field

from app.config.constantes import EstadoExtraccion


class FormularioSalida(BaseModel):
    extraccion_id: int
    documento_id: int
    documento: str
    paquete: str
    estado: EstadoExtraccion
    # `Any`: JSON Schema y datos con la forma del paquete; el cliente arma el formulario con ellos.
    json_schema: dict[str, Any] = Field(description="esquema del paquete: el formulario")
    propuesta: dict[str, Any] = Field(description="lo que leyó el LLM (puede no validar)")
    errores: list[str] = Field(description="por qué la propuesta no valida, si no valida")
    confirmados: dict[str, Any] | None


class RechazoSalida(BaseModel):
    extraccion_id: int
    documento_id: int
    documento_eliminado: bool = Field(
        description="el documento se borra: el mismo archivo puede volver a subirse"
    )


class ConfirmacionSalida(BaseModel):
    extraccion_id: int
    estado: EstadoExtraccion
    trozos: int = Field(description="trozos embebidos con los datos confirmados")
