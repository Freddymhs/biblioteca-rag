from pydantic import BaseModel, Field

from app.config.constantes import MAX_LARGO_PREGUNTA, MAX_LARGO_SLUG, PATRON_SLUG


class PreguntaEntrada(BaseModel):
    pregunta: str = Field(
        min_length=1, max_length=MAX_LARGO_PREGUNTA, examples=["¿Cuál es el Kc del olivo?"]
    )
    espacio: str = Field(max_length=MAX_LARGO_SLUG, pattern=PATRON_SLUG, examples=["laboral"])
    coleccion: str | None = Field(
        default=None,
        max_length=MAX_LARGO_SLUG,
        pattern=PATRON_SLUG,
        description="Sin colección, busca en todas las del espacio",
        examples=["agricultura"],
    )


class CitaSalida(BaseModel):
    documento_id: int
    documento: str = Field(description="nombre del archivo")
    pagina_inicio: int | None = Field(description="None en texto plano")
    pagina_fin: int | None = Field(description="igual a pagina_inicio si cabe en una página")
    fragmento: str
    distancia: float = Field(description="distancia coseno: 0 = idéntico")


class RespuestaSalida(BaseModel):
    respuesta: str
    sabe: bool = Field(description="False cuando la respuesta es «no lo sé»")
    citas: list[CitaSalida]
