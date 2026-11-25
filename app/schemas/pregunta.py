from pydantic import BaseModel, Field

from app.config.constantes import (
    MAX_LARGO_PREGUNTA,
    MAX_LARGO_SLUG,
    PATRON_SLUG,
    OrigenTrozo,
    RutaRespuesta,
)


class PreguntaEntrada(BaseModel):
    pregunta: str = Field(
        min_length=1, max_length=MAX_LARGO_PREGUNTA, examples=["¿Cuál es el Kc del olivo?"]
    )
    espacio: str = Field(max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG, examples=["intereses"])
    coleccion: str | None = Field(
        default=None,
        max_length=MAX_LARGO_SLUG,
        pattern=PATRON_SLUG,
        description="Sin colección, busca en todas las del espacio",
        examples=["agricultura"],
    )


DESCRIPCION_POR_ORIGEN = {
    OrigenTrozo.TEXTO: "copiado del documento",
    OrigenTrozo.VISION: "descripción generada por un modelo de visión",
    OrigenTrozo.DATOS: "datos estructurados confirmados por una persona",
}
DESCRIPCION_ORIGEN = " · ".join(f"{o.value}: {DESCRIPCION_POR_ORIGEN[o]}" for o in OrigenTrozo)


class CitaSalida(BaseModel):
    documento_id: int
    documento: str = Field(description="nombre del archivo")
    titulo: str = Field(description="título real del documento; si no tiene, el nombre del archivo")
    pagina_inicio: int | None = Field(description="None en texto plano")
    pagina_fin: int | None = Field(description="igual a pagina_inicio si cabe en una página")
    origen: OrigenTrozo = Field(description=DESCRIPCION_ORIGEN)
    fragmento: str
    distancia: float = Field(description="distancia coseno: 0 = idéntico")
    licencia: str | None = Field(
        default=None, description="licencia del documento (a citar si se reproduce el fragmento)"
    )
    fuente: str | None = Field(default=None, description="institución o publicación de origen")
    anno: int | None = Field(default=None, description="año de publicación")


class RespuestaSalida(BaseModel):
    respuesta: str
    sabe: bool = Field(description="False cuando la respuesta es «no lo sé»")
    citas: list[CitaSalida]
    ruta: RutaRespuesta = Field(
        description="semantica: búsqueda + LLM · sql: herramienta fija de un paquete de dominio"
    )
    herramienta: str | None = Field(description="herramienta SQL usada (ruta sql)")
