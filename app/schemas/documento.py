from datetime import datetime

from pydantic import BaseModel, Field

from app.config.constantes import TipoDocumento


class DocumentoRespuesta(BaseModel):
    id: int
    nombre_archivo: str
    tipo: TipoDocumento
    paginas: int | None = Field(description="None en texto plano")
    trozos: int
    creado_en: datetime


class DocumentoIngerido(DocumentoRespuesta):
    paginas_sin_texto: list[int] = Field(
        description="Páginas sin capa de texto: no se indexaron todavía (FASE_2)"
    )
