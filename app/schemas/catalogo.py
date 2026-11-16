from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config.constantes import MAX_LARGO_NOMBRE, MAX_LARGO_SLUG, PATRON_SLUG

Slug = Field(min_length=1, max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG, examples=["agricultura"])
Nombre = Field(min_length=1, max_length=MAX_LARGO_NOMBRE, examples=["Agricultura"])


class EspacioCrear(BaseModel):
    slug: str = Slug
    nombre: str = Nombre


class EspacioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nombre: str
    creado_en: datetime


class ColeccionCrear(BaseModel):
    slug: str = Slug
    nombre: str = Nombre
    paquete: str | None = Field(
        default=None,
        description="Paquete de dominio (ej. «facturas»): extracción, confirmación y SQL fijo",
    )


class ColeccionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    espacio: str = Field(description="slug del espacio")
    slug: str
    nombre: str
    paquete: str | None
    creado_en: datetime
