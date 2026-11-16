"""Conector a la API de resume (`fmarcosdev.api.resume`, NestJS).

Contrato leído de su código, no supuesto: `GET {base}/api/resume` devuelve `resume.json` (esquema
JSON Resume) sin envoltorio (`resume.controller.ts` → `getResume`; `main.ts` → prefijo `api`).
Cada sección que es lista produce un registro por elemento; cada sección objeto, uno solo.
"""

from typing import Any

import httpx

from app.conectores.base import ErrorConector, Registro
from app.config.constantes import TIMEOUT_CONECTOR_SEGUNDOS

RUTA_RESUME = "/api/resume"
NOMBRE = "resume"
SECCIONES_EXCLUIDAS = {"$schema", "meta"}  # metadatos del archivo, no conocimiento
# Claves que identifican un elemento de lista, en orden de preferencia (esquema JSON Resume).
CLAVES_IDENTIFICADORAS = ("name", "title", "institution", "organization", "language", "position")
# Si dos elementos de una sección comparten nombre (dos cargos en la misma empresa), se agregan
# estas claves al id. Si aun así se repiten, la fuente es ambigua: error, no se indexa a medias.
CLAVES_DESAMBIGUACION = ("position", "studyType", "area", "startDate", "date")
SEPARADOR_ID = "|"
SEPARADOR_LISTA = ", "


class ConectorResume:
    nombre = NOMBRE

    def __init__(self, base_url: str, cliente_http: httpx.Client | None = None) -> None:
        self._url = f"{base_url.rstrip('/')}{RUTA_RESUME}"
        self._http = cliente_http or httpx.Client(timeout=TIMEOUT_CONECTOR_SEGUNDOS)

    def registros(self) -> list[Registro]:
        resume = self._pedir()
        registros: list[Registro] = []
        for seccion in sorted(set(resume) - SECCIONES_EXCLUIDAS):
            registros.extend(_registros_de_seccion(seccion, resume[seccion]))
        return registros

    # `Any`: JSON de la fuente; su forma se valida aquí mismo.
    def _pedir(self) -> dict[str, Any]:
        try:
            respuesta = self._http.get(self._url)
        except httpx.HTTPError as error:
            raise ErrorConector(f"La API de resume no respondió: {error}") from error
        if respuesta.status_code != httpx.codes.OK:
            raise ErrorConector(f"La API de resume respondió {respuesta.status_code}")
        try:
            cuerpo = respuesta.json()
        except ValueError as error:
            raise ErrorConector("La API de resume no respondió JSON") from error
        if not isinstance(cuerpo, dict):
            raise ErrorConector("La API de resume no respondió un objeto JSON Resume")
        return cuerpo


def _registros_de_seccion(seccion: str, valor: Any) -> list[Registro]:
    if isinstance(valor, dict):
        return [Registro(seccion, seccion, _texto(seccion, valor))] if valor else []
    if isinstance(valor, list):
        nombres = _nombres_unicos(seccion, valor)
        return [
            Registro(f"{seccion}:{nombre}", f"{seccion}: {nombre}", _texto(seccion, elemento))
            for nombre, elemento in zip(nombres, valor, strict=True)
        ]
    return []


def _nombres_unicos(seccion: str, elementos: list[Any]) -> list[str]:
    base = [_identificador(elemento, indice) for indice, elemento in enumerate(elementos)]
    repetidos = {nombre for nombre in base if base.count(nombre) > 1}
    nombres = [
        SEPARADOR_ID.join([nombre, *_desambiguadores(elemento)]) if nombre in repetidos else nombre
        for nombre, elemento in zip(base, elementos, strict=True)
    ]
    indistinguibles = sorted({f"{seccion}:{n}" for n in nombres if nombres.count(n) > 1})
    if indistinguibles:
        raise ErrorConector(f"La fuente tiene elementos indistinguibles: {indistinguibles}")
    return nombres


def _desambiguadores(elemento: Any) -> list[str]:
    if not isinstance(elemento, dict):
        return []
    return [str(elemento[clave]) for clave in CLAVES_DESAMBIGUACION if elemento.get(clave)]


def _identificador(elemento: Any, indice: int) -> str:
    if isinstance(elemento, dict):
        for clave in CLAVES_IDENTIFICADORAS:
            if elemento.get(clave):
                return str(elemento[clave])
    return str(indice)  # sin nombre: el orden es lo único estable que hay


def _texto(seccion: str, valor: Any) -> str:
    """Claves ordenadas: el hash del texto no debe cambiar si la fuente reordena claves."""
    return "\n".join([f"Sección: {seccion}", *_lineas(valor, prefijo="")])


def _lineas(valor: Any, prefijo: str) -> list[str]:
    if isinstance(valor, dict):
        lineas: list[str] = []
        for clave in sorted(valor):
            lineas.extend(_lineas(valor[clave], f"{prefijo}{clave}"))
        return lineas
    if isinstance(valor, list):
        if all(not isinstance(elemento, dict | list) for elemento in valor):
            unido = SEPARADOR_LISTA.join(str(elemento) for elemento in valor)
            return [f"{prefijo}: {unido}"] if unido else []
        return [linea for elemento in valor for linea in _lineas(elemento, f"{prefijo}.")]
    if valor in (None, ""):
        return []
    return [f"{prefijo}: {valor}"]
