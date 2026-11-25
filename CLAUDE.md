# CLAUDE.md — biblioteca-rag

## Reglas del proyecto

### Alembic — registro de modelos

Al agregar un modelo SQLAlchemy nuevo, importarlo en `app/models/__init__.py`.
Es el único punto donde Alembic autogenerate detecta cambios de schema.
Sin este import, `alembic revision --autogenerate` genera migraciones vacías.

### Python — imports tardíos intencionales

Imports que deben ir después de `sys.path.insert` o `load_dotenv` necesitan
`# noqa: E402` más un comentario que explique por qué el orden es intencionalmente
no estándar. Sin esto, ruff los marca como errores en lugar de advertencias suprimidas.

### Datos de producción sin ruta en la API — el cambio va en una migración

Si un cambio sobre datos (renombrar un espacio, marcar una colección) no tiene ruta en la API, se aplica con una
migración Alembic **idempotente** (`WHERE` sobre el estado de origen y `NOT EXISTS` sobre el de destino) y su test,
no con un `UPDATE` a mano, que no deja huella en git. Una migración ya aplicada no se edita: se agrega otra.
*Real 2026-11-25: `laboral` → `intereses` se aplicó a mano en producción y se registró después en
`alembic/versions/*_espacio_laboral_pasa_a_intereses.py`.*
