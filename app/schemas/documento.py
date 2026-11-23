import unicodedata
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.config.constantes import (
    ANNO_MAXIMO_DOCUMENTO,
    ANNO_MINIMO_DOCUMENTO,
    CATEGORIA_UNICODE_CONTROL,
    MAX_LARGO_FUENTE_DOCUMENTO,
    MAX_LARGO_LICENCIA,
    MAX_LARGO_TITULO_DOCUMENTO,
    TipoDocumento,
)


# `object`: un BeforeValidator recibe la entrada cruda, antes de que pydantic la tipe.
def _texto_de_metadato(valor: object) -> object:
    """K4: sin espacios en los bordes, y lo que queda vacío es ausente (None): un título en blanco
    no deja una cita sin título, cae al nombre del archivo (decisión: ausente, no 422, igual que
    el campo de formulario vacío de 6.1). Un carácter de control, NUL incluido, es un error."""
    if not isinstance(valor, str):
        return valor
    recortado = valor.strip()
    if any(unicodedata.category(caracter) == CATEGORIA_UNICODE_CONTROL for caracter in recortado):
        raise ValueError("no puede tener caracteres de control")
    return recortado or None


TextoDeMetadato = Annotated[str | None, BeforeValidator(_texto_de_metadato)]


class MetadatosDocumento(BaseModel):
    """6.1: metadatos opcionales de un documento. Los campos de más (de un catálogo) se ignoran."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    titulo: TextoDeMetadato = Field(default=None, max_length=MAX_LARGO_TITULO_DOCUMENTO)
    fuente: TextoDeMetadato = Field(default=None, max_length=MAX_LARGO_FUENTE_DOCUMENTO)
    anno: int | None = Field(default=None, ge=ANNO_MINIMO_DOCUMENTO, le=ANNO_MAXIMO_DOCUMENTO)


class DocumentoRespuesta(BaseModel):
    id: int
    nombre_archivo: str
    tipo: TipoDocumento
    paginas: int | None = Field(description="None en texto plano")
    trozos: int
    creado_en: datetime
    licencia: str | None = Field(description="licencia declarada, ej. «CC BY-NC-SA 4.0»")
    licencia_verificada: bool = Field(
        description="True solo si una persona la verificó: sin eso el documento nunca es público"
    )
    titulo: str | None = Field(default=None, description="título real, si llegó al subir")
    fuente: str | None = Field(default=None, description="institución o publicación de origen")
    anno: int | None = Field(default=None, description="año de publicación")


class LicenciaFijar(BaseModel):
    licencia: str | None = Field(
        max_length=MAX_LARGO_LICENCIA,
        examples=["CC BY-NC-SA 4.0"],
        description="None: sin licencia",
    )
    verificada: bool = Field(description="Verificada por una persona (decisión, no inferencia)")


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
