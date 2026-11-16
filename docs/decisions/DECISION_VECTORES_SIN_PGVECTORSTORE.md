# DECISION: vectores con SQLAlchemy + `pgvector`, sin `PGVectorStore`

**Fecha**: 2026-11-15 · **Estado**: aceptada (sin Freddy, revisable) · **Cambia**: `_CONCEPTO.md`, fila «Framework RAG» (`langchain-postgres` → `PGVectorStore`)

## Contexto

El concepto elige `PGVectorStore` de `langchain-postgres`. La FASE_1 exige además: esquema propio en Alembic
(espacio → colección → documento → trozo) y **documento + trozos en una sola transacción**.

## Decisión

La tabla `trozo` es un modelo SQLAlchemy con columna `pgvector.sqlalchemy.Vector(1024)` e índice HNSW declarado en el
modelo y creado por la migración. La búsqueda es un `SELECT … ORDER BY embedding <=> :vector` con JOIN a documento,
colección y espacio. LangChain se usa solo en sus interfaces de proveedor (`Embeddings`, `BaseChatModel`).

## Por qué

- `PGVectorStore` escribe con su propio motor (`PGEngine`) y su propia conexión: no puede unirse a la transacción de
  SQLAlchemy donde se inserta el documento. Con él, un fallo a mitad deja un documento sin trozos o trozos huérfanos.
- La cita es un JOIN en la misma base; con `PGVectorStore` los datos del documento irían como metadatos duplicados.
- Alembic queda como única fuente del esquema (el test `test_modelos_y_migraciones_coinciden` lo vigila).

## Consecuencias

- Se pierde la búsqueda híbrida ya hecha de `PGVectorStore`; si se necesita, es SQL sobre la misma tabla.
- La dimensión 1024 queda fija en la columna: otro modelo de embeddings con otra dimensión exige migración.
- `psycopg` 3 sigue siendo el driver (FASE_0), así que adoptar `langchain-postgres` más adelante no cambia nada.
