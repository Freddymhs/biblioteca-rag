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
    paginas_sin_texto: list[int] = Field(description="Páginas sin capa de texto (todas)")
    paginas_por_vision: list[int] = Field(
        description="De esas, las que describió el modelo de visión (quedan buscables)"
    )
    paginas_en_blanco: list[int] = Field(description="De esas, las vacías: no se indexan")
    extraccion_id: int | None = Field(
        default=None,
        description="Colección con paquete: extracción a confirmar (nada se embebe antes)",
    )
    paginas_sin_indexar: list[int] = Field(
        description="De esas, las que no se pudieron describir (visión desactivada o sin respuesta)"
    )
