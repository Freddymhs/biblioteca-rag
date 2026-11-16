from datetime import datetime

from pydantic import BaseModel, Field

from app.config.constantes import EstadoTrabajo, TipoTrabajo


class TrabajoRespuesta(BaseModel):
    id: int
    espacio: str
    coleccion: str
    tipo: TipoTrabajo
    estado: EstadoTrabajo = Field(description="derivado de los contadores")
    total: int | None = Field(description="None mientras no se conoce (sincronización)")
    procesados: int
    ingeridos: int
    duplicados: int = Field(description="mismo contenido que otro documento de la colección")
    sin_cambios: int = Field(description="sincronización: registros que no cambiaron en la fuente")
    rechazados: int
    errores: int
    eliminados: int = Field(description="sincronización: registros que ya no están en la fuente")
    trozos: int
    ultimo_error: str | None
    creado_en: datetime
    actualizado_en: datetime


class SincronizacionEntrada(BaseModel):
    conector: str = Field(examples=["resume"], description="nombre de un conector registrado")
    permitir_vaciar: bool = Field(
        default=False,
        description="Si la fuente responde sin registros, borrar la colección (si no, es error)",
    )
