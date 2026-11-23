# Despliegue público (tarea 4.8): pasos escritos, NO ejecutados

> BLOQUEADA 2026-11-16: faltan de Freddy el túnel de Cloudflare (token), el dominio y la orden de exponer. Nada de
> esto se corrió: ni en el Mac Mini ni en Cloudflare. El archivo `docker-compose.prod.yml` está escrito y validado con
> `docker compose config` (tests `tests/test_contenedor.py` y `tests/test_auditoria_fase4.py`), no levantado.
> Actualizado el 2026-11-16 con las correcciones de la auditoría de seguridad (G1–G13).

## Qué queda expuesto y qué no

- **Entrada única:** `cloudflared`, que abre una conexión saliente hacia Cloudflare. El anfitrión no publica ningún
  puerto (`ports: !reset []` en api, db y redis).
- **Redes (G11):** `cloudflared` solo comparte la red `borde` con la API. La base y Redis están en `datos`, interna y
  sin salida a internet. La API y el worker salen a los proveedores (embeddings, LLM) por `salida`.
- **Sin API key:** `GET /api/publico/colecciones`, `GET /api/publico/buscar`, `POST /api/publico/preguntas` y el MCP en
  `/mcp`. Leen con el usuario `biblioteca_web` del grupo `biblioteca_publico` (RLS: solo colecciones públicas y
  documentos con licencia verificada), con consultas cortadas a los 5 s y con:
  - cuerpo de hasta 16 KB (G1);
  - por minuto y por IP (IPv6 agrupada por /64): 30 búsquedas y 5 respuestas;
  - por día: 500 búsquedas y 20 respuestas por IP; 10.000 búsquedas y 200 respuestas en total (G2, G3). Un 404 o un
    422 no gasta la cuota diaria;
  - 2 respuestas con LLM a la vez; la tercera recibe 503 al instante (G4).
  Los errores de los proveedores salen con un mensaje genérico; el detalle, al log (G9).
- **Con API key (`X-API-Key`, 32 caracteres o más, G10):** todo el resto de `/api`, también leer (ahí están las
  colecciones personales). Sin clave se responde 401 **antes de leer el cuerpo** (G1).
- `/docs` y `/openapi.json` quedan visibles: documentan los dos grupos. Lo decide Freddy (H1 de la auditoría).

## Usuarios de Postgres (G6, G7, G8)

| Usuario | Quién lo crea | Para qué | Sin |
|---|---|---|---|
| `postgres` | la imagen | la extensión `vector` y administrar | — |
| `biblioteca` | `docker/initdb/02-usuario-app.sh` (volumen nuevo, con `APP_DB_PASSWORD`) | dueño: migra y ejecuta la API y el worker | SUPERUSER, BYPASSRLS, CREATEDB |
| `biblioteca_web` | `docker/arrancar-api.sh` (cada arranque, idempotente) | lo público y el MCP | SUPERUSER, BYPASSRLS, CREATEROLE, CREATEDB; es miembro de `biblioteca_publico` |

- Al arrancar, la API comprueba que `biblioteca_web` no sea superusuario, no tenga BYPASSRLS, no sea el dueño y sea
  del grupo; si no, **no arranca**.
- Sin `DATABASE_URL_PUBLICA`, tampoco arranca. El respaldo de desarrollo (`PERMITIR_PUBLICO_SIN_USUARIO=true`) usa la
  conexión del dueño con `role=biblioteca_publico`: un `SET ROLE` al dueño lo deshace, y producción lo pone en
  `false`.
- **Volumen que ya existía** (los scripts de `initdb` corren solo con un volumen nuevo): sus tablas son de
  `postgres`. Lo limpio es volcar sin dueños y restaurar como `biblioteca` en un volumen nuevo (sin probar aquí: la
  prueba real, con un volumen nuevo, es `test_g8_la_app_migra_y_corre_sin_ser_superusuario`):

  ```
  docker compose exec db pg_dump -U postgres --no-owner --no-privileges -Fc biblioteca_rag > respaldo.dump
  # volumen nuevo con APP_DB_PASSWORD (initdb crea `biblioteca`), y luego:
  docker compose exec -T db pg_restore -U biblioteca -d biblioteca_rag --no-owner < respaldo.dump
  ```

  Los roles y permisos del grupo público los vuelve a poner la API al arrancar (migración + `biblioteca_web`).

## Antes de empezar (decisiones de Freddy)

1. Licencias: marcar como verificadas las que se publican (`docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md`). Sin
   esto, la colección `agricultura` es pública pero no muestra ningún documento.
2. Términos del plan de MiniMax para uso en una app (DECISION_SERVICIO_PUBLICO): `POST /api/publico/preguntas` y la
   tool `preguntar` usan el LLM. Si no se confirman, poner `LIMITE_RESPUESTAS_DIARIAS=0` y queda solo la búsqueda.
3. Dominio (ej. `biblioteca.<dominio>`), y versión de `cloudflared` a fijar.

## Pasos (en el Mac Mini, cuando se autorice)

1. En el panel de Cloudflare: Zero Trust → Networks → Tunnels → crear un túnel administrado por panel. Copiar su
   token. Agregar el hostname público `DOMINIO_PUBLICO` → servicio `http://api:8000`.
2. En `.env` del Mac Mini (nunca en el repo), cada clave con `python -c "import secrets; print(secrets.token_urlsafe(32))"`:

   ```
   API_KEY=<32 caracteres o más>
   REDIS_PASSWORD=<...>
   POSTGRES_PASSWORD=<...>           # sin valor por defecto en producción
   APP_DB_PASSWORD=<...>             # el dueño `biblioteca`
   PUBLICO_DB_PASSWORD=<...>         # el usuario `biblioteca_web` de lo público
   DOMINIO_PUBLICO=biblioteca.<dominio>
   CLOUDFLARED_VERSION=<versión fijada>
   CLOUDFLARE_TUNNEL_TOKEN=<token del paso 1>
   ```

   Compose no arranca si falta cualquiera. `DATABASE_URL` y `DATABASE_URL_PUBLICA` las arma compose con esas claves.
3. Levantar sin el túnel. La API migra, crea o pone al día `biblioteca_web` y verifica sus atributos antes de servir:

   ```
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build db redis api worker
   ```

4. Comprobar adentro, antes de exponer:

   ```
   docker compose exec api python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8000/health').status)"
   docker compose exec db psql -U postgres -d biblioteca_rag -c "\du biblioteca biblioteca_web"
   ```

   (`biblioteca` sin «Superuser»; `biblioteca_web` miembro de `biblioteca_publico`), y que `GET /api/espacios` sin
   clave responde 401.
5. Recién ahí, el túnel: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d cloudflared`.
6. Desde fuera: `curl https://$DOMINIO_PUBLICO/api/publico/colecciones` (200) y `curl https://$DOMINIO_PUBLICO/api/espacios`
   (401). Un agente MCP apunta a `https://$DOMINIO_PUBLICO/mcp` (el MCP acepta ese Host porque
   `docker-compose.prod.yml` arma `MCP_HOSTS_PERMITIDOS` con `DOMINIO_PUBLICO`).

## Sin verificar (depende de Cloudflare)

- Si Cloudflare reemplaza un `CF-Connecting-IP` que mande el cliente (de eso depende que el límite por IP no se
  falsifique detrás del túnel), su tope de cuerpo y si acumula un envío en trozos antes de pasarlo.

## Para volver atrás

`docker compose -f docker-compose.yml -f docker-compose.prod.yml stop cloudflared` corta la exposición sin tocar lo
demás. Borrar el túnel en el panel invalida el token.

## Despliegue vigente (2026-11-22, commit `ffd876d`)

- Mac Mini, `~/apps/biblioteca-rag/`: `repo/` (clon), `repo/.env` (copia de `env.produccion`, chmod 600, ahí está la
  `API_KEY`), `compose.macmini.yml` (tercera capa: imagen x86 cargada, API en `127.0.0.1:3015`).
- Corre: `docker compose -p biblioteca-rag -f docker-compose.yml -f docker-compose.prod.yml -f ../compose.macmini.yml
  up -d --no-build api` (levanta api, db, redis; worker, jaeger y cloudflared del compose no).
- Imagen: se construye en el ThinkPad (`docker build --platform linux/amd64 -t biblioteca-rag-api:produccion .`) y se
  carga con `docker save … | ssh mac-mini docker load`.
- Datos: `pg_dump --data-only --exclude-table=alembic_version` de `biblioteca_rag_prod` (ThinkPad), restaurado con
  `pg_restore --data-only --disable-triggers --single-transaction` como `postgres`: 89 documentos (79 públicos),
  11.628 trozos, revisión `c7a2d4e8f613`.
- Túnel: el cloudflared del anfitrión, no el del compose. `~/.cloudflared/config.yml` (respaldo
  `config.yml.bak-2026-11-22`) entrega `biblioteca.fmarcos.dev` → `http://localhost:3015`.
- Verificado desde fuera: `/health` y `/api/publico/colecciones` 200, `/api/espacios` sin clave 401, `/docs` 404, MCP
  `initialize` 200 en `/mcp`. La respuesta redactada depende del saldo de MiniMax (punto 15 de los pendientes).
