from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.config.constantes import MAX_LARGO_PREGUNTA, MAX_LARGO_SLUG, PATRON_SLUG
from app.schemas.pregunta import CitaSalida

MENSAJE_COLECCION_SIN_ESPACIO = "una colección se nombra junto a su espacio"

Espacio = Field(default=None, max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG, examples=["laboral"])
Coleccion = Field(
    default=None,
    max_length=MAX_LARGO_SLUG,
    pattern=PATRON_SLUG,
    description="Exige `espacio`. Sin colección ni espacio: todas las públicas",
    examples=["agricultura"],
)


class ColeccionPublica(BaseModel):
    espacio: str
    slug: str
    nombre: str
    documentos: int = Field(description="documentos públicos (licencia verificada)")


class BusquedaSalida(BaseModel):
    """Fragmentos con cita, sin LLM. Nunca el documento completo."""

    fragmentos: list[CitaSalida]


class PreguntaPublicaEntrada(BaseModel):
    pregunta: str = Field(
        min_length=1, max_length=MAX_LARGO_PREGUNTA, examples=["¿Cuál es el Kc del olivo?"]
    )
    espacio: str | None = Espacio
    coleccion: str | None = Coleccion

    @model_validator(mode="after")
    def _coleccion_con_espacio(self) -> Self:
        if self.coleccion is not None and self.espacio is None:
            raise ValueError(MENSAJE_COLECCION_SIN_ESPACIO)
        return self
