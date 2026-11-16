#!/bin/sh
# G8: en producción la app no es superusuario. Si el contenedor recibe APP_DB_PASSWORD, se crea
# `biblioteca`: dueño de la base (migra y ejecuta), sin SUPERUSER ni BYPASSRLS; con CREATEROLE
# solo para crear el grupo público y su usuario con login. `postgres` queda para la extensión
# (01-vector.sql) y la administración. Corre una sola vez, al crear el volumen.
set -eu
if [ -z "${APP_DB_PASSWORD:-}" ]; then
    echo "02-usuario-app: sin APP_DB_PASSWORD, la app usa el usuario del contenedor (desarrollo)"
    exit 0
fi
psql -v ON_ERROR_STOP=1 -v clave="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE biblioteca LOGIN NOSUPERUSER NOBYPASSRLS CREATEROLE NOCREATEDB PASSWORD :'clave';
SELECT format('ALTER DATABASE %I OWNER TO biblioteca', current_database()) \gexec
SQL
