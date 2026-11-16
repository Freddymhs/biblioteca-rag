#!/bin/sh
# B6: la API migra la base antes de servir. Solo la API: el worker usa otro comando (compose).
# G6: después crea o pone al día el usuario con login de lo público (idempotente; se niega si
# fuera el dueño o un superusuario). Sin ese usuario, la API no arranca.
# Un solo proceso de uvicorn: dos cargarían Docling dos veces (lo pesado va por la cola, D1).
set -eu
alembic upgrade head
python -m app.cli.usuario_publico
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 "$@"
