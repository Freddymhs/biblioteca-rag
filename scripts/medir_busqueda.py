"""Latencia de la búsqueda REAL de la app (`app.services.pregunta.buscar`) en una base DESECHABLE.

    uv run python scripts/medir_busqueda.py [--trozos 25000]

Levanta un Postgres con pgvector (testcontainers), lo migra hasta `head` y carga `--trozos` trozos
en UNA colección pública con licencia verificada: todos pasan el filtro, que es el peor caso de la
búsqueda exacta. Los vectores son al azar (la latencia de la búsqueda exacta no depende de su
forma) y cada texto mide lo que un trozo real de 512 tokens. Mide la mediana de `buscar` en lo
privado (espacio + colección) y en lo público (rol `biblioteca_publico`, RLS de verdad).

No lee ni escribe ninguna otra base: sirve para comparar dos versiones de `buscar` (auditoría K2).
"""

import argparse
import os
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from testcontainers.community.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
IMAGEN_PGVECTOR = "pgvector/pgvector:pg16"
SEMILLA = 7
TROZOS_POR_DEFECTO = 25000
TROZOS_POR_DOCUMENTO = 500
CARACTERES_POR_TROZO = 2000  # un trozo real de 512 tokens de bge-m3
LOTE_INSERCION = 1000
PREGUNTAS = 5
CALENTAMIENTO = 3
REPETICIONES = 15
MS_POR_SEGUNDO = 1000
ESPACIO = "medicion"
COLECCION = "corpus"
MODELO = "medicion:aleatorio"
LICENCIA = "CC BY 4.0"


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--trozos", type=int, default=TROZOS_POR_DEFECTO)
    trozos = argumentos.parse_args().trozos
    with PostgresContainer(IMAGEN_PGVECTOR, driver="psycopg") as pg:
        url = pg.get_connection_url()
        # Antes de importar la app: settings y engine leen el entorno al importarse. Lo vacío
        # pisa lo que diga el `.env` local (ninguna base ni exportador de trazas de verdad).
        os.environ.update(
            DATABASE_URL=url,
            DATABASE_URL_PUBLICA="",
            PERMITIR_PUBLICO_SIN_USUARIO="true",
            TRAZAS_OTLP_URL="",
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=RAIZ,
            env=os.environ,
            check=True,
        )
        sys.path.insert(0, str(RAIZ))  # el script corre desde scripts/: la app vive en la raíz
        return _medir(trozos)


def _medir(trozos: int) -> int:
    # Imports tardíos intencionales: la app lee DATABASE_URL al importarse (fijada en `main`).
    from sqlalchemy import text

    from app.config.constantes import ROL_PUBLICO
    from app.config.database import SessionLocal
    from app.services.pregunta import buscar

    generador = np.random.default_rng(SEMILLA)
    with SessionLocal() as db:
        _cargar(db, trozos, generador)
        db.execute(text("ANALYZE"))
        db.commit()
        print(f"trozos: {trozos} · todos en {ESPACIO}/{COLECCION} (pública, verificada)")
        vectores = [_vector_al_azar(generador) for _ in range(PREGUNTAS)]

        def privada(vector: list[float]) -> int:
            return len(buscar(db, vector, ESPACIO, COLECCION, MODELO))

        def publica(vector: list[float]) -> int:
            with db.begin_nested():
                db.execute(text(f"SET LOCAL ROLE {ROL_PUBLICO}"))
                devueltos = len(buscar(db, vector, None, None, MODELO, solo_publico=True))
                db.execute(text("RESET ROLE"))
            return devueltos

        _informar("privada (espacio + colección)", privada, vectores)
        _informar("pública (rol biblioteca_publico)", publica, vectores)
    return 0


def _cargar(db: "Session", trozos: int, generador: np.random.Generator) -> None:
    from sqlalchemy import insert

    from app.config.constantes import LARGO_SHA256_HEX, TipoDocumento
    from app.models import Documento, Trozo
    from app.services import catalogo

    catalogo.crear_espacio(db, ESPACIO, ESPACIO)
    destino = catalogo.crear_coleccion(db, ESPACIO, COLECCION, COLECCION)
    catalogo.publicar_coleccion(db, ESPACIO, COLECCION, True)
    documentos = [
        Documento(
            coleccion_id=destino.id,
            nombre_archivo=f"doc-{numero}.txt",
            hash_contenido=str(numero).zfill(LARGO_SHA256_HEX),
            tipo=TipoDocumento.TEXTO,
            licencia=LICENCIA,
            licencia_verificada=True,
        )
        for numero in range(-(-trozos // TROZOS_POR_DOCUMENTO))  # división hacia arriba
    ]
    db.add_all(documentos)
    db.flush()
    texto = "x" * CARACTERES_POR_TROZO
    filas = [
        {
            "documento_id": documentos[orden // TROZOS_POR_DOCUMENTO].id,
            "orden": orden,
            "texto": texto,
            "embedding": _vector_al_azar(generador),
            "embedding_model": MODELO,
        }
        for orden in range(trozos)
    ]
    for inicio in range(0, trozos, LOTE_INSERCION):
        db.execute(insert(Trozo), filas[inicio : inicio + LOTE_INSERCION])
    db.commit()


def _vector_al_azar(generador: np.random.Generator) -> list[float]:
    from app.config.constantes import DIMENSION_EMBEDDING

    vector = generador.standard_normal(DIMENSION_EMBEDDING)
    return list(vector / np.linalg.norm(vector))


def _informar(
    nombre: str, buscar: Callable[[list[float]], int], vectores: list[list[float]]
) -> None:
    for vector in vectores[:CALENTAMIENTO]:
        buscar(vector)
    tiempos = []
    devueltos: set[int] = set()
    for _ in range(REPETICIONES):
        for vector in vectores:
            inicio = time.perf_counter()
            devueltos.add(buscar(vector))
            tiempos.append((time.perf_counter() - inicio) * MS_POR_SEGUNDO)
    cuantiles = statistics.quantiles(tiempos, n=10)
    print(
        f"  {nombre:34} mediana {statistics.median(tiempos):7.1f} ms · p10 {cuantiles[0]:7.1f} · "
        f"p90 {cuantiles[-1]:7.1f} · {len(tiempos)} búsquedas · devuelve {sorted(devueltos)}"
    )


if __name__ == "__main__":
    sys.exit(main())
