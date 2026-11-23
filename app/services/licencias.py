"""Licencias desde una tabla con veredicto (FASE_6, 6.7). Genérico: cualquier tabla Markdown con
las columnas «Archivo», «Propuesta» y «Veredicto». La de agricultura es
`docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md`.

K3: se lee solo el bloque contiguo de filas bajo la cabecera; cada fila tiene tantas celdas como
la cabecera, y archivo, propuesta y veredicto no vacíos. El veredicto es
«decisión[: motivo] [(quién, cuándo)]» y la decisión es exactamente «publicar» o «no publicar».
Un archivo repetido es un error. Todo error nombra el archivo de la tabla y la línea.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constantes import (
    COLUMNA_ARCHIVO_LICENCIAS,
    COLUMNA_PROPUESTA_LICENCIAS,
    COLUMNA_VEREDICTO_LICENCIAS,
    MAX_LARGO_LICENCIA,
    SEPARADOR_MOTIVO_VEREDICTO,
    VEREDICTO_NO_PUBLICAR,
    VEREDICTO_PUBLICAR,
)
from app.models import Coleccion, Documento

SEPARADOR_CELDAS = "|"
# La línea que separa la cabecera de las filas: |---|:--:|---|
PATRON_SEPARADOR_TABLA = re.compile(r"^\|(\s*:?-+:?\s*\|)+$")
# La firma final de un veredicto: «(Freddy, 2026-11-16)».
PATRON_FIRMA_VEREDICTO = re.compile(r"\s*\([^()]*\)\s*$")


@dataclass(frozen=True)
class FilaLicencia:
    archivo: str
    propuesta: str
    publicar: bool


@dataclass(frozen=True)
class ResumenLicencias:
    filas: int
    verificadas: int
    sin_publicar: int
    sin_documento: list[str]  # filas de la tabla que no están en la colección
    sin_fila: list[str]  # documentos de la colección que la tabla no nombra (quedan como estaban)

    @property
    def calzadas(self) -> int:
        """Filas de la tabla que nombran un documento de la colección."""
        return self.verificadas + self.sin_publicar


def leer_tabla_licencias(ruta: Path) -> list[FilaLicencia]:
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    cabecera_en = next(
        (
            indice
            for indice, linea in enumerate(lineas)
            if _es_fila(linea) and COLUMNA_VEREDICTO_LICENCIAS in _celdas(linea)
        ),
        None,
    )
    if cabecera_en is None:
        raise ValueError(
            f"{ruta.name}: no hay una tabla con la columna «{COLUMNA_VEREDICTO_LICENCIAS}»"
        )
    cabecera = _celdas(lineas[cabecera_en])
    faltantes = [
        columna
        for columna in (COLUMNA_ARCHIVO_LICENCIAS, COLUMNA_PROPUESTA_LICENCIAS)
        if columna not in cabecera
    ]
    if faltantes:
        raise ValueError(f"{ruta.name}: a la tabla le faltan las columnas {faltantes}")
    filas: list[FilaLicencia] = []
    for numero, linea in _bloque_bajo_la_cabecera(lineas, cabecera_en):
        fila = _fila(ruta, numero, linea, cabecera)
        if any(anterior.archivo == fila.archivo for anterior in filas):
            raise ValueError(f"{ruta.name}, línea {numero}: «{fila.archivo}» aparece dos veces")
        filas.append(fila)
    return filas


def aplicar_licencias(
    db: Session, coleccion: Coleccion, filas: list[FilaLicencia], *, aplicar: bool
) -> ResumenLicencias:
    """Sin `aplicar`, solo calcula el resumen: nada se escribe."""
    por_archivo = {fila.archivo: fila for fila in filas}
    documentos = list(db.scalars(select(Documento).where(Documento.coleccion_id == coleccion.id)))
    nombres = {documento.nombre_archivo for documento in documentos}
    verificadas = sin_publicar = 0
    for documento in documentos:
        fila = por_archivo.get(documento.nombre_archivo)
        if fila is None:
            continue
        verificadas += fila.publicar
        sin_publicar += not fila.publicar
        if aplicar:
            documento.licencia = fila.propuesta[:MAX_LARGO_LICENCIA]
            documento.licencia_verificada = fila.publicar
    if aplicar:
        db.commit()
    return ResumenLicencias(
        filas=len(filas),
        verificadas=verificadas,
        sin_publicar=sin_publicar,
        sin_documento=sorted(set(por_archivo) - nombres),
        sin_fila=sorted(nombres - set(por_archivo)),
    )


def _bloque_bajo_la_cabecera(lineas: list[str], cabecera_en: int) -> list[tuple[int, str]]:
    """Las filas contiguas bajo la cabecera, con su número de línea (desde 1). La primera línea
    que no es fila corta el bloque: una segunda tabla más abajo no se mezcla."""
    bloque: list[tuple[int, str]] = []
    for indice in range(cabecera_en + 1, len(lineas)):
        linea = lineas[indice]
        if not _es_fila(linea):
            break
        if not PATRON_SEPARADOR_TABLA.match(linea.strip()):
            bloque.append((indice + 1, linea))
    return bloque


def _fila(ruta: Path, numero: int, linea: str, cabecera: list[str]) -> FilaLicencia:
    donde = f"{ruta.name}, línea {numero}"
    celdas = _celdas(linea)
    if len(celdas) != len(cabecera):
        raise ValueError(f"{donde}: tiene {len(celdas)} celdas y la cabecera {len(cabecera)}")
    valores = dict(zip(cabecera, celdas, strict=True))
    archivo = valores[COLUMNA_ARCHIVO_LICENCIAS]
    propuesta = valores[COLUMNA_PROPUESTA_LICENCIAS]
    veredicto = valores[COLUMNA_VEREDICTO_LICENCIAS]
    leidas = {
        COLUMNA_ARCHIVO_LICENCIAS: archivo,
        COLUMNA_PROPUESTA_LICENCIAS: propuesta,
        COLUMNA_VEREDICTO_LICENCIAS: veredicto,
    }
    vacias = [columna for columna, valor in leidas.items() if not valor]
    if vacias:
        raise ValueError(f"{donde}: celdas vacías en {vacias}")
    return FilaLicencia(archivo=archivo, propuesta=propuesta, publicar=_publica(donde, veredicto))


def _publica(donde: str, veredicto: str) -> bool:
    """«publicar (Freddy, …)» → True; «no publicar: derechos reservados (…)» → False."""
    sin_firma = PATRON_FIRMA_VEREDICTO.sub("", veredicto)
    decision = sin_firma.partition(SEPARADOR_MOTIVO_VEREDICTO)[0].strip().lower()
    if decision == VEREDICTO_PUBLICAR:
        return True
    if decision == VEREDICTO_NO_PUBLICAR:
        return False
    raise ValueError(
        f"{donde}: veredicto «{veredicto}» desconocido; la decisión es «{VEREDICTO_PUBLICAR}» o "
        f"«{VEREDICTO_NO_PUBLICAR}», con motivo y firma opcionales"
    )


def _es_fila(linea: str) -> bool:
    return linea.strip().startswith(SEPARADOR_CELDAS)


def _celdas(linea: str) -> list[str]:
    """Quita UN separador a cada borde: `||` es una celda vacía, no se pierde."""
    interior = linea.strip().removeprefix(SEPARADOR_CELDAS).removesuffix(SEPARADOR_CELDAS)
    return [celda.strip() for celda in interior.split(SEPARADOR_CELDAS)]
