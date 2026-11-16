-- Corre una sola vez, al crear el volumen de datos. La migración inicial repite
-- `CREATE EXTENSION IF NOT EXISTS vector` para bases que no nacen de este compose.
CREATE EXTENSION IF NOT EXISTS vector;
