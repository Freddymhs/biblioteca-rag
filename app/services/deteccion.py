"""Detección de tipo por contenido, nunca por extensión, y hash para no ingerir duplicados."""

import hashlib
from dataclasses import dataclass

from app.common.errors import payload_too_large, unprocessable
from app.config.constantes import (
    BYTES_BUSQUEDA_FIRMA_PDF,
    FIRMA_PDF,
    MAX_BYTES_SUBIDA,
    TipoDocumento,
)

# Proporción mínima de caracteres legibles para aceptar un archivo como texto plano.
PROPORCION_MINIMA_LEGIBLE = 0.95
BYTE_NULO = b"\x00"


@dataclass(frozen=True)
class ArchivoDetectado:
    tipo: TipoDocumento
    hash_contenido: str


def detectar(contenido: bytes) -> ArchivoDetectado:
    """Clasifica el archivo o lanza 413/422 si no se puede ingerir."""
    if len(contenido) > MAX_BYTES_SUBIDA:
        raise payload_too_large(f"El archivo supera el máximo de {MAX_BYTES_SUBIDA} bytes")
    if not contenido.strip():
        raise unprocessable("El archivo está vacío")

    tipo = _tipo_por_contenido(contenido)
    if tipo is None:
        raise unprocessable("Tipo de archivo no soportado: se aceptan PDF y texto plano UTF-8")

    return ArchivoDetectado(tipo=tipo, hash_contenido=hash_contenido(contenido))


def hash_contenido(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _tipo_por_contenido(contenido: bytes) -> TipoDocumento | None:
    if FIRMA_PDF in contenido[:BYTES_BUSQUEDA_FIRMA_PDF]:
        return TipoDocumento.PDF
    if _es_texto_plano(contenido):
        return TipoDocumento.TEXTO
    return None


def _es_texto_plano(contenido: bytes) -> bool:
    if BYTE_NULO in contenido:
        return False
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        return False
    legibles = sum(1 for caracter in texto if caracter.isprintable() or caracter.isspace())
    return legibles / len(texto) >= PROPORCION_MINIMA_LEGIBLE
