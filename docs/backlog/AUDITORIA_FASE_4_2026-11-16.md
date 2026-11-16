# Auditoría de seguridad de la FASE_4 — 2026-11-16, antes de su commit

Auditó una sesión distinta a la que escribió el código, leyendo completos los archivos de seguridad, sus tests y los
documentos de despliegue. `make check` ya pasaba (285 tests, 7 saltados). Los puntos G5, G6 y G2 se comprobaron
después abriendo el archivo; G5, además, ejecutando la función.

**Sin hallazgos críticos.** No se encontró fuga de datos privados ni forma de saltarse la clave:

- El RLS encadena bien: un trozo solo se lee si su documento tiene licencia verificada y su colección es pública.
- Al rol público solo se le conceden columnas no sensibles de `documento`; `extraccion`, `trabajo` y
  `alembic_version` no tienen permiso alguno.
- Las 16 operaciones de `/api` fuera de `/api/publico` exigen la clave (comprobado enumerando el OpenAPI de la app).
- La ruta pública no pasa por el enrutador de cálculo SQL y el LLM no tiene herramientas.

## G. Se corrige antes del commit

Cada punto se cierra con un test que falle sin el arreglo y `make check` en verde. Marcar la casilla al cerrarlo.

- [x] **G1 El cuerpo se lee antes de pedir la clave y antes del límite** — `main.py`: FastAPI parsea el cuerpo antes
  de resolver las dependencias. Un anónimo puede enviar hasta 101 MB a una ruta privada (1 GB a `…/lotes`) y se
  vuelcan a disco antes del 401; lo mismo en `POST /api/publico/preguntas` y `/mcp` antes del 429. Validar la clave
  en un middleware ASGI antes de leer el cuerpo, tope chico de cuerpo para lo público y el MCP, y contar bytes al
  recibir cuando no hay `Content-Length`.
- [x] **G2 Una sola IP agota la cuota diaria de todos** — `app/providers/limites.py`: con 5 por minuto se consumen
  las 200 respuestas diarias en 40 minutos, y el contador sube aunque la petición termine en 404 o 422. Tope diario
  por IP, y contar después de validar.
- [x] **G3 La búsqueda no tiene techo global** — `app/providers/limites.py`: solo límite por IP, y con IPv6 cada
  dirección cuenta aparte. Gasta la cuota de embeddings sin límite. Tope diario global de búsquedas y agrupar IPv6
  por /64.
- [x] **G4 Lo público puede dejar sin hilos a lo privado** — `app/routers/publico.py` y `app/mcp_publico.py`: las
  rutas públicas comparten el pool de hilos con lo privado y con `/health`, y el LLM puede tardar 120 s. Semáforo de
  concurrencia para las llamadas públicas al LLM, con 503 o 429 cuando está lleno.
- [x] **G5 El delimitador de fragmentos se puede saltar** — `app/services/pregunta.py`, `_neutralizar`: solo
  reemplaza `</fragmento>` exacto. `< /fragmento>` y `＜/fragmento＞` pasan intactos (comprobado ejecutando la
  función). Escapar todo `<` y `>` del fragmento y de la pregunta, o delimitar con un valor aleatorio por petición.
- [x] **G6 Lo público cae en silencio a la conexión del dueño** — `app/config/database.py`, `_engine_publico`: sin
  `DATABASE_URL_PUBLICA` usa la conexión del dueño con `role=`, que se puede deshacer dentro de la sesión; en compose
  el dueño es superusuario. Fallar al arrancar salvo que una variable explícita de desarrollo lo permita, y avisar
  en el log.
- [x] **G7 Nada impide que el usuario público sea el dueño o un superusuario** — `app/cli/usuario_publico.py`: la
  CLI debe negarse si el usuario es el dueño o tiene `rolsuper` o `rolbypassrls`, y fijar
  `NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB`. Al arrancar, comprobar lo mismo sobre el motor público.
- [x] **G8 La API corre como superusuario de Postgres** — `docker-compose.yml` y `docker-compose.prod.yml`: en
  producción, exigir `POSTGRES_PASSWORD` y separar el usuario de migración del de ejecución (dueño sin SUPERUSER).
- [x] **G9 Los errores del proveedor llegan al anónimo** — `app/common/errors.py`: el 502 devuelve el texto del
  proveedor (cuerpo de Cloudflare, mensajes del LLM). En lo público, mensaje genérico; el detalle va al log.
- [x] **G10 Clave sin largo mínimo** — `app/common/auth.py` y `app/config/settings.py`: exigir al menos 32
  caracteres (hoy un test usa `"x"`).
- [x] **G11 El túnel comparte red con la base y Redis** — `docker-compose.prod.yml`: red aparte que comparta solo
  `cloudflared` con `api`.
- [x] **G12 Tests de seguridad que no pueden fallar** — `tests/test_mcp.py`: pasa aunque la IP fuera siempre
  «desconocida» y no prueba que REST y MCP compartan contador. `tests/test_rls.py`: solo prueba una de las columnas
  no concedidas y no prueba deshacer el rol en la conexión de respaldo. Falta el test de cuerpo grande sin clave.
- [x] **G13 Defensa en profundidad** — `ENABLE ROW LEVEL SECURITY` sin política en `extraccion` y `trabajo` (hoy
  dependen solo de que no haya permiso); `statement_timeout` para el rol público; impedir publicar una colección con
  paquete; el aviso de «embebida con otro modelo» no debe decirle a un anónimo qué modelos hay ni qué comando correr.

## H. Abierto, para Freddy

- **H1 `/docs`, `/redoc` y `/openapi.json` quedan públicos** y describen las rutas de administración. Decide él si se
  cierran en producción.
- **H2 Con el índice HNSW, el filtro de lo público se aplica después de buscar**: si los vecinos cercanos son
  privados, la búsqueda pública devuelve menos resultados. Es el mismo problema de `DECISION_HNSW_FILTROS.md`.

## No verificado por la auditoría

- Nada se ejecutó contra Postgres ni Redis reales: políticas y permisos se revisaron leyendo el código y los tests.
- Si Cloudflare sobrescribe un `CF-Connecting-IP` enviado por el cliente, su tope de cuerpo y si acumula el envío en
  trozos. De eso depende cuánto mitiga el túnel el punto G1.
- Si Postgres deja en su log la contraseña del `ALTER ROLE … PASSWORD`.
