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
