"""Catálogo JSON de metadatos por nombre de archivo (FASE_6, 6.1). Genérico: sirve para cualquier
colección. Dos formas aceptadas:

- lista de objetos, cada uno con `archivo` (el nombre exacto) y sus metadatos;
- objeto que mapea nombre de archivo → metadatos.

De cada entrada se toman `titulo`, `fuente` y `anno`; cualquier otro campo se ignora. Los valida
`MetadatosDocumento` (K4): un título o una fuente en blanco quedan ausentes, y un carácter de
control rechaza la entrada nombrándola.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.config.constantes import CLAVE_ARCHIVO_CATALOGO
from app.schemas.documento import MetadatosDocumento

# `object`: el JSON de un catálogo, antes de validarlo entrada por entrada.
Entrada = dict[str, object]


def leer_catalogo(ruta: Path) -> dict[str, MetadatosDocumento]:
    """Nombre de archivo → metadatos. ValueError (nombrando la entrada) si algo no valida."""
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    pares = _pares(contenido)
    catalogo: dict[str, MetadatosDocumento] = {}
    for archivo, entrada in pares:
        if archivo in catalogo:
            raise ValueError(f"{ruta.name}: «{archivo}» aparece dos veces")
        try:
            catalogo[archivo] = MetadatosDocumento.model_validate(entrada)
        except ValidationError as error:
            raise ValueError(f"{ruta.name}: la entrada de «{archivo}» no vale: {error}") from error
    return catalogo


def _pares(contenido: object) -> list[tuple[str, Entrada]]:
    if isinstance(contenido, dict):
        return [(str(archivo), _objeto(archivo, entrada)) for archivo, entrada in contenido.items()]
    if isinstance(contenido, list):
        pares = []
        for posicion, entrada in enumerate(contenido):
            objeto = _objeto(f"posición {posicion}", entrada)
            archivo = objeto.get(CLAVE_ARCHIVO_CATALOGO)
            if not isinstance(archivo, str) or not archivo:
                raise ValueError(f"la entrada en la posición {posicion} no tiene «archivo»")
            pares.append((archivo, objeto))
        return pares
    raise ValueError("el catálogo debe ser una lista de objetos o un objeto archivo → metadatos")


def _objeto(donde: object, entrada: object) -> Entrada:
    if not isinstance(entrada, dict):
        raise ValueError(f"la entrada de «{donde}» no es un objeto")
    return entrada
