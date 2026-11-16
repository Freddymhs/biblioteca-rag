from pydantic import BaseModel, Field


class RechazosSalida(BaseModel):
    busqueda: int = Field(description="429 a colecciones y búsquedas (por minuto o cuota diaria)")
    respuesta: int = Field(description="429 a respuestas redactadas con LLM")


class UsoDelDiaSalida(BaseModel):
    """Lo público de un día (REST y MCP juntos). Sin IPs ni preguntas: solo conteos."""

    fecha: str = Field(description="AAAA-MM-DD, UTC")
    busquedas: int = Field(
        description="búsquedas respondidas (un 404, 422 o 502 del proveedor no cuenta)"
    )
    respuestas: int = Field(
        description="respuestas redactadas entregadas (un 404, 422 o 502 del proveedor no cuenta)"
    )
    rechazos_429: RechazosSalida
