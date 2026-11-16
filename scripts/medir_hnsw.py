"""Mide el índice HNSW con filtros (auditoría B3) sobre una base DESECHABLE.

    uv run python scripts/medir_hnsw.py [--ruido 20000]

Copia los trozos reales de la base de `docker compose` (solo lectura), agrega `--ruido` vectores
aleatorios en OTRO espacio (lo que habrá con muchas colecciones) y compara, por pregunta, los
5 trozos de la búsqueda exacta contra HNSW tal cual y con `hnsw.iterative_scan`. Imprime cuántos
trozos devuelve cada modo y su recall@5 contra el exacto.
"""

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

import psycopg
from langchain_ollama import OllamaEmbeddings
from pgvector.psycopg import register_vector
from testcontainers.community.postgres import PostgresContainer

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = "postgresql://postgres:postgres@127.0.0.1:5432/biblioteca_rag"
DIMENSION = 1024
K = 5
SEMILLA = 7
SIGMA = 0.02  # ruido por dimensión del vector cercano
PREGUNTAS = [
    "¿Qué hortalizas se consideran plantas duras frente a las heladas?",
    "¿Cuál es la demanda hídrica diaria del nogal en Choapa interior en diciembre?",
    "¿Cómo se cultivan las tunas para tener buenos ingresos?",
]
# Misma forma que `app.services.pregunta.buscar`: filtro por espacio y modelo, orden por coseno.
CONSULTA = """
SELECT t.id FROM trozo t
JOIN documento d ON t.documento_id = d.id
JOIN coleccion c ON d.coleccion_id = c.id
JOIN espacio e ON c.espacio_id = e.id
WHERE e.slug = %(espacio)s AND t.embedding_model = %(modelo)s
ORDER BY t.embedding <=> %(vector)s LIMIT %(k)s
"""
# «forzado» simula lo que pasará cuando el planificador elija el índice (más datos por espacio).
FORZAR_INDICE = ["SET LOCAL enable_seqscan = off", "SET LOCAL enable_sort = off"]
MODOS = {
    "exacto": ["SET LOCAL enable_indexscan = off"],
    "hnsw": [],
    "hnsw+iterativo": ["SET LOCAL hnsw.iterative_scan = strict_order"],
    "forzado": FORZAR_INDICE,
    "forzado+iterativo": [*FORZAR_INDICE, "SET LOCAL hnsw.iterative_scan = strict_order"],
    "forzado+iter+tuplas": [
        *FORZAR_INDICE,
        "SET LOCAL hnsw.iterative_scan = strict_order",
        "SET LOCAL hnsw.max_scan_tuples = 1000000",
    ],
    "forzado+relajado": [
        *FORZAR_INDICE,
        "SET LOCAL hnsw.iterative_scan = relaxed_order",
        "SET LOCAL hnsw.max_scan_tuples = 1000000",
    ],
    "forzado+ef400": [*FORZAR_INDICE, "SET LOCAL hnsw.ef_search = 400"],
    "forzado+iter+memoria": [
        *FORZAR_INDICE,
        "SET LOCAL hnsw.iterative_scan = strict_order",
        "SET LOCAL hnsw.max_scan_tuples = 1000000",
        "SET LOCAL hnsw.scan_mem_multiplier = 64",
    ],
}


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--ruido", type=int, default=20000)
    ruido = argumentos.parse_args().ruido

    with psycopg.connect(COMPOSE) as origen:
        filas = origen.execute(
            "SELECT texto, embedding::text, embedding_model FROM trozo"
        ).fetchall()
    modelo = filas[0][2]
    print(f"trozos reales: {len(filas)} · modelo: {modelo} · ruido: {ruido}")

    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        url = pg.get_connection_url()
        entorno = {**os.environ, "DATABASE_URL": url}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=RAIZ, env=entorno, check=True
        )
        crudo = url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(crudo, autocommit=True) as db:
            register_vector(db)
            _cargar(db, filas, modelo, ruido)
            vectores = OllamaEmbeddings(model="bge-m3").embed_documents(PREGUNTAS)
            for pregunta, vector in zip(PREGUNTAS, vectores, strict=True):
                _medir(db, pregunta, vector, modelo)
    return 0


def _cargar(db: psycopg.Connection, filas: list, modelo: str, ruido: int) -> None:
    ids = {}
    for espacio in ("laboral", "ruido"):
        ids[espacio] = _id(
            db.execute(
                "INSERT INTO espacio (slug, nombre) VALUES (%s, %s) RETURNING id",
                (espacio, espacio),
            )
        )
    documentos = {}
    for espacio in ids:
        coleccion = _id(
            db.execute(
                "INSERT INTO coleccion (espacio_id, slug, nombre) "
                "VALUES (%s, 'c', 'c') RETURNING id",
                (ids[espacio],),
            )
        )
        documentos[espacio] = _id(
            db.execute(
                "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo) "
                "VALUES (%s, %s, %s, 'txt') RETURNING id",
                (coleccion, espacio, espacio.ljust(64, "0")),
            )
        )
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO trozo (documento_id, orden, texto, embedding, embedding_model) "
            "VALUES (%s, %s, %s, %s::vector, %s)",
            [(documentos["laboral"], i, t, v, modelo) for i, (t, v, _) in enumerate(filas)],
        )
        generador = random.Random(SEMILLA)
        reales = [_a_lista(v) for _, v, _ in filas]
        cursor.executemany(
            "INSERT INTO trozo (documento_id, orden, texto, embedding, embedding_model) "
            "VALUES (%s, %s, 'ruido', %s, %s)",
            [
                (documentos["ruido"], i, _cercano(generador.choice(reales), generador), modelo)
                for i in range(ruido)
            ],
        )
    db.execute("ANALYZE trozo")


def _id(cursor: psycopg.Cursor) -> int:
    fila = cursor.fetchone()
    if fila is None:
        raise RuntimeError("INSERT … RETURNING id no devolvió fila")
    return fila[0]


def _a_lista(texto: str) -> list[float]:
    return [float(x) for x in texto.strip("[]").split(",")]


def _cercano(base: list[float], generador: random.Random) -> list[float]:
    """Otra colección del mismo tema: un vector real perturbado (coseno ≈ 0,85 con el original).

    Con vectores al azar el ruido nunca compite (en 1024 dimensiones queda a distancia ≈ 1)."""
    import numpy as np

    perturbado = np.array(base) + np.array([generador.gauss(0, SIGMA) for _ in range(DIMENSION)])
    return list(perturbado / np.linalg.norm(perturbado))


def _medir(db: psycopg.Connection, pregunta: str, vector: list[float], modelo: str) -> None:
    import numpy as np

    parametros = {"espacio": "laboral", "modelo": modelo, "vector": np.array(vector), "k": K}
    resultados: dict[str, list[int]] = {}
    planes: dict[str, bool] = {}
    for modo, ajustes in MODOS.items():
        with db.transaction():
            for ajuste in ajustes:
                db.execute(ajuste)
            resultados[modo] = [fila[0] for fila in db.execute(CONSULTA, parametros)]
            plan = " ".join(f[0] for f in db.execute("EXPLAIN " + CONSULTA, parametros))
            planes[modo] = "ix_trozo_embedding_hnsw" in plan
    exacto = set(resultados["exacto"])
    print(f"\n{pregunta}")
    for modo, ids in resultados.items():
        recall = len(exacto & set(ids)) / len(exacto) if exacto else 0
        indice = "índice HNSW" if planes[modo] else "sin índice"
        print(f"  {modo:20} {indice:12} devuelve {len(ids)} de {K} · recall@{K} {recall:.2f}")


if __name__ == "__main__":
    sys.exit(main())
