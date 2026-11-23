"""Mide el índice HNSW con filtros (auditoría B3, tarea 6.3) sobre una base DESECHABLE.

    uv run python scripts/medir_hnsw.py [--ruido 20000] [--revision head]

`--revision` migra la base desechable hasta esa revisión de Alembic: así se mide el esquema de
antes y el de después de un cambio (6.3: antes = 9c4d2e7f1a36, después = head).

Copia los trozos reales de la base de `docker compose` (solo lectura) a una colección PÚBLICA con
licencia verificada, y agrega `--ruido` vectores del mismo tema (copias perturbadas de los reales)
en OTRO espacio, privado: lo que habrá con muchas colecciones parecidas. Por pregunta compara los
5 trozos de la búsqueda exacta contra el índice HNSW forzado, con y sin `hnsw.iterative_scan`, en:

- **privado**: filtro por espacio (como `/api/preguntas`), por JOIN o, si el esquema lo tiene, por
  `trozo.espacio_id` (y con un índice parcial por espacio);
- **público**: con el rol `biblioteca_publico` (el RLS filtra) y el filtro explícito de lo público.

Imprime, por consulta y modo, cuántos trozos devuelve y su recall@5 contra el exacto.
"""

import argparse
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import LiteralString, cast

import numpy as np
import psycopg
from langchain_ollama import OllamaEmbeddings
from pgvector.psycopg import register_vector
from testcontainers.community.postgres import PostgresContainer

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = "postgresql://postgres:postgres@127.0.0.1:5432/biblioteca_rag"
DIMENSION = 1024
K = 5
SEMILLA = 7
SIGMA = 0.02  # ruido por dimensión del vector cercano (coseno ≈ 0,85 con el original)
ROL_PUBLICO = "biblioteca_publico"
PREGUNTAS = [
    "¿Qué hortalizas se consideran plantas duras frente a las heladas?",
    "¿Cuál es la demanda hídrica diaria del nogal en Choapa interior en diciembre?",
    "¿Cómo se cultivan las tunas para tener buenos ingresos?",
]
ORDEN = "ORDER BY t.embedding <=> %(vector)s LIMIT %(k)s"
# Las consultas: (nombre, SQL, ¿con el rol público?, ¿necesita las columnas desnormalizadas?).
CONSULTAS = [
    (
        "privado · JOIN (antes)",
        "SELECT t.id FROM trozo t JOIN documento d ON t.documento_id = d.id "
        "JOIN coleccion c ON d.coleccion_id = c.id JOIN espacio e ON c.espacio_id = e.id "
        f"WHERE e.slug = %(espacio)s AND t.embedding_model = %(modelo)s {ORDEN}",
        False,
        False,
    ),
    (
        "público · JOIN + RLS (antes)",
        "SELECT t.id FROM trozo t JOIN documento d ON t.documento_id = d.id "
        "JOIN coleccion c ON d.coleccion_id = c.id "
        f"WHERE c.publica AND d.licencia_verificada AND t.embedding_model = %(modelo)s {ORDEN}",
        True,
        False,
    ),
    (
        "privado · trozo.espacio_id",
        "SELECT t.id FROM trozo t "
        "WHERE t.espacio_id = (SELECT id FROM espacio WHERE slug = %(espacio)s) "
        f"AND t.embedding_model = %(modelo)s {ORDEN}",
        False,
        True,
    ),
    (
        "público · solo RLS en trozo",
        f"SELECT t.id FROM trozo t WHERE t.embedding_model = %(modelo)s {ORDEN}",
        True,
        False,
    ),
    (
        "privado · CTE exacta (la app, 6.3)",
        "WITH filtrados AS MATERIALIZED (SELECT t.id, t.embedding <=> %(vector)s AS d FROM trozo t "
        "WHERE t.espacio_id = (SELECT id FROM espacio WHERE slug = %(espacio)s) "
        "AND t.embedding_model = %(modelo)s) SELECT id FROM filtrados ORDER BY d LIMIT %(k)s",
        False,
        True,
    ),
    (
        "público · CTE exacta + RLS (la app, 6.3)",
        "WITH filtrados AS MATERIALIZED (SELECT t.id, t.embedding <=> %(vector)s AS d FROM trozo t "
        "WHERE t.documento_id = ANY(CAST((SELECT array_agg(d.id) FROM documento d "
        "JOIN coleccion c ON c.id = d.coleccion_id WHERE c.publica AND d.licencia_verificada) "
        "AS integer[])) AND t.embedding_model = %(modelo)s) "
        "SELECT id FROM filtrados ORDER BY d LIMIT %(k)s",
        True,
        False,
    ),
    (
        "público · ANY(documentos públicos) + RLS",
        "SELECT t.id FROM trozo t WHERE t.documento_id = ANY(CAST((SELECT array_agg(d.id) "
        "FROM documento d JOIN coleccion c ON c.id = d.coleccion_id "
        "WHERE c.publica AND d.licencia_verificada) AS integer[])) "
        f"AND t.embedding_model = %(modelo)s {ORDEN}",
        True,
        False,
    ),
]
FORZAR_INDICE = ["SET LOCAL enable_seqscan = off", "SET LOCAL enable_sort = off"]
MODOS = {
    # Lo que hace la app desde 6.3: sin recorrer el índice HNSW (enable_indexscan off); el filtro
    # usa los btree de trozo (bitmap scan, que sigue permitido) y la distancia se calcula exacta.
    "exacto": ["SET LOCAL enable_indexscan = off"],
    "forzado": FORZAR_INDICE,
    "forzado+estricto": [*FORZAR_INDICE, "SET LOCAL hnsw.iterative_scan = strict_order"],
    "forzado+relajado": [*FORZAR_INDICE, "SET LOCAL hnsw.iterative_scan = relaxed_order"],
    # max_scan_tuples (20.000 por defecto) corta el recorrido iterativo: con 20.000 vecinos de
    # otra colección más cerca que los buscados, no llega a ellos.
    "forzado+estricto+tuplas": [
        *FORZAR_INDICE,
        "SET LOCAL hnsw.iterative_scan = strict_order",
        "SET LOCAL hnsw.max_scan_tuples = 1000000",
        "SET LOCAL hnsw.scan_mem_multiplier = 8",
    ],
}
INDICE_PARCIAL = "ix_medicion_parcial_laboral"
REPETICIONES = 5
MS_POR_SEGUNDO = 1000


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--ruido", type=int, default=20000)
    argumentos.add_argument("--revision", default="head", help="revisión de Alembic a medir")
    argumentos.add_argument(
        "--ruido-en-el-espacio",
        action="store_true",
        help="el ruido en el MISMO espacio (otra colección): mide la búsqueda exacta sobre mucho",
    )
    leidos = argumentos.parse_args()
    ruido, revision, mismo_espacio = leidos.ruido, leidos.revision, leidos.ruido_en_el_espacio

    with psycopg.connect(COMPOSE) as origen:
        filas = origen.execute(
            "SELECT texto, embedding::text, embedding_model FROM trozo"
        ).fetchall()
    modelo = filas[0][2]
    print(
        f"trozos reales: {len(filas)} · modelo: {modelo} · ruido: {ruido} · esquema: {revision} · "
        f"ruido en el mismo espacio: {'sí' if mismo_espacio else 'no'}"
    )

    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        url = pg.get_connection_url()
        entorno = {**os.environ, "DATABASE_URL": url}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=RAIZ,
            env=entorno,
            check=True,
        )
        crudo = url.replace("postgresql+psycopg://", "postgresql://")
        # prepare_threshold=None: psycopg prepara en el servidor la consulta que se repite más de 5
        # veces, y desde ahí corre el plan preparado bajo OTRO modo (otros SET LOCAL). Medido: con
        # eso el «exacto» de la segunda pregunta usaba el plan del índice forzado.
        with psycopg.connect(crudo, autocommit=True, prepare_threshold=None) as db:
            register_vector(db)
            desnormalizado = _tiene_columnas(db)
            print(f"esquema con trozo.espacio_id: {'sí' if desnormalizado else 'no'}")
            espacio_real = _cargar(db, filas, modelo, ruido, mismo_espacio)
            vectores = OllamaEmbeddings(model="bge-m3").embed_documents(PREGUNTAS)
            consultas = [c for c in CONSULTAS if desnormalizado or not c[3]]
            for pregunta, vector in zip(PREGUNTAS, vectores, strict=True):
                print(f"\n{pregunta}")
                for nombre, sql, publico, _ in consultas:
                    _medir(db, nombre, sql, publico, vector, modelo)
            if desnormalizado:
                print(f"\n— con un índice HNSW parcial WHERE espacio_id = {espacio_real} —")
                db.execute(
                    _sql(
                        f"CREATE INDEX {INDICE_PARCIAL} ON trozo USING hnsw "
                        f"(embedding vector_cosine_ops) WHERE espacio_id = {espacio_real}"
                    )
                )
                db.execute("ANALYZE trozo")
                parcial = (
                    "privado · índice parcial",
                    f"SELECT t.id FROM trozo t WHERE t.espacio_id = {espacio_real} "
                    f"AND t.embedding_model = %(modelo)s {ORDEN}",
                )
                for pregunta, vector in zip(PREGUNTAS, vectores, strict=True):
                    print(f"\n{pregunta}")
                    _medir(db, parcial[0], parcial[1], False, vector, modelo)
    return 0


def _tiene_columnas(db: psycopg.Connection) -> bool:
    fila = db.execute(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'trozo' AND column_name = 'espacio_id'"
    ).fetchone()
    return bool(fila and fila[0])


def _cargar(
    db: psycopg.Connection, filas: list, modelo: str, ruido: int, mismo_espacio: bool
) -> int:
    """Reales en laboral/c (pública, licencia verificada); ruido en una colección privada de otro
    espacio o, con `mismo_espacio`, de laboral."""
    ids = {}
    espacios: dict[str, int] = {}
    for espacio, publica in (("laboral", True), ("ruido", False)):
        espacio_destino = "laboral" if mismo_espacio else espacio
        if espacio_destino not in espacios:
            espacios[espacio_destino] = _id(
                db.execute(
                    "INSERT INTO espacio (slug, nombre) VALUES (%s, %s) RETURNING id",
                    (espacio_destino, espacio_destino),
                )
            )
        espacio_id = espacios[espacio_destino]
        coleccion = _id(
            db.execute(
                "INSERT INTO coleccion (espacio_id, slug, nombre, publica) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (espacio_id, espacio, espacio, publica),
            )
        )
        ids[espacio] = (
            espacio_id,
            _id(
                db.execute(
                    "INSERT INTO documento (coleccion_id, nombre_archivo, hash_contenido, tipo, "
                    "licencia_verificada) VALUES (%s, %s, %s, 'txt', %s) RETURNING id",
                    (coleccion, espacio, espacio.ljust(64, "0"), publica),
                )
            ),
        )
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO trozo (documento_id, orden, texto, embedding, embedding_model) "
            "VALUES (%s, %s, %s, %s::vector, %s)",
            [(ids["laboral"][1], i, t, v, modelo) for i, (t, v, _) in enumerate(filas)],
        )
        generador = random.Random(SEMILLA)
        reales = [_a_lista(v) for _, v, _ in filas]
        cursor.executemany(
            "INSERT INTO trozo (documento_id, orden, texto, embedding, embedding_model) "
            "VALUES (%s, %s, 'ruido', %s, %s)",
            [
                (ids["ruido"][1], i, _cercano(generador.choice(reales), generador), modelo)
                for i in range(ruido)
            ],
        )
    db.execute("ANALYZE trozo")
    return ids["laboral"][0]


def _sql(texto: str) -> LiteralString:
    """El SQL de este script se arma solo con sus constantes (ningún dato de afuera); psycopg pide
    LiteralString para no interpolar entrada externa por descuido."""
    return cast(LiteralString, texto)


def _id(cursor: psycopg.Cursor) -> int:
    fila = cursor.fetchone()
    if fila is None:
        raise RuntimeError("INSERT … RETURNING id no devolvió fila")
    return fila[0]


def _a_lista(texto: str) -> list[float]:
    return [float(x) for x in texto.strip("[]").split(",")]


def _cercano(base: list[float], generador: random.Random) -> list[float]:
    """Otra colección del mismo tema: un vector real perturbado. Con vectores al azar el ruido
    nunca compite (en 1024 dimensiones queda a distancia ≈ 1) y no se mide nada."""
    perturbado = np.array(base) + np.array([generador.gauss(0, SIGMA) for _ in range(DIMENSION)])
    return list(perturbado / np.linalg.norm(perturbado))


def _medir(
    db: psycopg.Connection, nombre: str, sql: str, publico: bool, vector: list[float], modelo: str
) -> None:
    parametros = {"espacio": "laboral", "modelo": modelo, "vector": np.array(vector), "k": K}
    resultados: dict[str, list[int]] = {}
    con_indice: dict[str, bool] = {}
    milisegundos: dict[str, float] = {}
    for modo, ajustes in MODOS.items():
        with db.transaction():
            if publico:
                db.execute(_sql(f"SET LOCAL ROLE {ROL_PUBLICO}"))
            for ajuste in ajustes:
                db.execute(_sql(ajuste))
            tiempos = []
            for _ in range(REPETICIONES):
                inicio = time.perf_counter()
                resultados[modo] = [fila[0] for fila in db.execute(_sql(sql), parametros)]
                tiempos.append((time.perf_counter() - inicio) * MS_POR_SEGUNDO)
            milisegundos[modo] = statistics.median(tiempos)
            plan = " ".join(f[0] for f in db.execute(_sql("EXPLAIN " + sql), parametros))
            con_indice[modo] = "using ix_trozo_embedding_hnsw" in plan or INDICE_PARCIAL in plan
    exacto = set(resultados["exacto"])
    print(f"  {nombre}")
    for modo, ids in resultados.items():
        recall = len(exacto & set(ids)) / len(exacto) if exacto else 0
        indice = "índice HNSW" if con_indice[modo] else "sin índice"
        print(
            f"    {modo:24} {indice:12} devuelve {len(ids)} de {K} · recall@{K} {recall:.2f} · "
            f"{milisegundos[modo]:.1f} ms"
        )


if __name__ == "__main__":
    sys.exit(main())
