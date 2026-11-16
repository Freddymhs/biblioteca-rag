# Informe FASE_4 — SERVICIO PÚBLICO (7/8, 4.8 bloqueada) + 7 puntos de auditorías

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Sin git (lo hace la sesión supervisora).

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 4.1 RLS | Migración `5b7c1e9d4a20`: rol de grupo `biblioteca_publico` (sin login) con `SELECT` sobre `espacio`, `coleccion`, `trozo` y solo algunas columnas de `documento` (no `estructura`, que es el texto completo, ni el hash ni el id externo). RLS en esas cuatro tablas: ve colecciones `publica` y documentos con `licencia_verificada`. Nada sobre `extraccion`, `trabajo` ni `alembic_version`. Lo público entra con un usuario con login miembro del grupo (`DATABASE_URL_PUBLICA`, creado con `python -m app.cli.usuario_publico`). Sin esa URL la API no arranca (G6); el respaldo de desarrollo, con `PERMITIR_PUBLICO_SIN_USUARIO=true` |
| 4.2 Flags | `coleccion.publica` y `documento.licencia` + `licencia_verificada` (por defecto, no). La misma migración marca pública `laboral/agricultura`; `sobre-mi` queda privada. `PATCH …/colecciones/{c}` publica y `PUT …/documentos/{id}/licencia` registra el veredicto |
| 4.3 Búsqueda pública | `GET /api/publico/colecciones` y `GET /api/publico/buscar`: fragmentos con cita (documento, páginas, licencia), sin LLM, nunca el documento completo |
| 4.4 Límite | `POST /api/publico/preguntas` (respuesta redactada). Contadores en Redis: por IP por minuto (búsqueda 30, respuesta 5) y tope diario global de respuestas (200). 429 al pasarlos; sin Redis, 503 (fail-closed) con un mensaje que no dice host ni puerto |
| 4.5 API key | `X-API-Key` contra `API_KEY` de `.env`, comparada en tiempo constante sobre el SHA-256 de cada lado (así tampoco se filtra el largo). La exige **todo** `/api` salvo `/api/publico`, también para leer. Sin `API_KEY` configurada: 503 |
| 4.6 Licencias | Tabla de los 89 documentos en `LICENCIAS_AGRICULTURA_2026-11-16.md`: evidencia citada, propuesta por reglas fijas y veredicto «sin verificar» en todos. Ninguno es público hasta que Freddy decida |
| 4.7 MCP | `/mcp` (streamable HTTP, sin estado, JSON) con el SDK oficial `mcp` 2.3.0 (`MCPServer`, documentación leída con context7). Solo `buscar` y `preguntar`, con `readOnlyHint`. Mismos servicios, sesión pública y límite por IP que REST. Un error de dominio vuelve como `isError` con su código. Hosts permitidos: `MCP_HOSTS_PERMITIDOS` |
| 4.8 Exposición | **BLOQUEADA**: falta el túnel, el dominio y la orden de exponer. Escritos sin ejecutar: `docker-compose.prod.yml` (ningún puerto publicado, entrada solo por `cloudflared`) y `docs/DESPLIEGUE_PUBLICO.md` |

Sumados de auditorías anteriores:

| Punto | Arreglo |
|---|---|
| B5 | Cada fragmento va entre `<fragmento n="…">…</fragmento>` y la pregunta entre `<pregunta>`; el sistema dice que el contenido no es instrucción. Un `</fragmento>` o `</pregunta>` dentro del texto queda neutralizado (`‹/fragmento>`) |
| B6 | La imagen migra al arrancar (`docker/arrancar-api.sh`), corre 1 proceso de uvicorn, tiene `HEALTHCHECK` contra `/health` y trae los modelos de Docling y el tokenizador (`app.cli.precargar_modelos` al construir). El worker desactiva ese healthcheck |
| B7 | `SECRET_KEY` eliminada (la reemplaza `API_KEY`). `ollama` y `anthropic` ya estaban declarados en `pyproject.toml` |
| D1 | `POST …/documentos` responde 413 con un archivo de más de 10 MB o un PDF de más de 30 páginas, y apunta a `…/lotes`. Contar páginas no convierte nada |
| D6 | Redis con `--requirepass`; compose no arranca sin `REDIS_PASSWORD`; la cola y el límite entran con la clave en `REDIS_URL` |
| F1 | Un cálculo cita como mucho 20 documentos y lo dice: «(Se citan 20 de 25 documentos.)» |
| F4 | Un lote a una colección con paquete es 422 antes de tocar la cola o el disco |

Criterios de aceptación: los cuatro cerrados con tests (401, colección privada invisible para el rol público, 429,
agente externo por MCP).

## Cómo se verificó

- `make check` → ruff `All checks passed!`, pyright `0 errors`, pytest **285 passed, 7 skipped** (eran 219; los 7
  son las preguntas de oro, que necesitan una API viva).
- **RLS con roles reales** (`tests/test_rls.py`): un usuario con login creado con la función de la CLI, conexión
  propia y datos confirmados de verdad. Por SQL directo no ve la colección privada ni el documento sin licencia, y no
  puede leer `estructura`, `extraccion` ni `trabajo`. Tampoco puede escribir ni escalar: `SET ROLE` al dueño y
  `RESET ROLE` dan `permission denied`.
- **Rojo a propósito** (mutaciones revertidas; `grep MUTACION` = 0; con `PYTHONDONTWRITEBYTECODE`):
  - RLS: política de colección en `true`, `GRANT SELECT` a todas las columnas de `documento`, `GRANT ALL` (con
    UPDATE/DELETE): rojo.
  - Auth: un router fuera del grupo privado, comparación siempre verdadera: rojo.
  - Público: sin filtro explícito, sin límite, sin neutralizar, confiar siempre en `CF-Connecting-IP`, una ruta
    pública con la sesión del dueño: rojo.
  - D1, F1 y F4 sin su guardia: rojo. MCP sin límite y MCP con `read_only_hint=False`: rojo.
  - **Sobrevivieron dos, equivalentes por diseño**:
    1. La política de `trozo` sin la condición de licencia: la subconsulta sobre `documento` ya pasa por su RLS.
    2. El MCP sin el filtro explícito: lo cubre el RLS, porque los tests corren con el rol real.
- **Contenedor** (`docker build` + red Docker desechable, sin puertos publicados): migró las 8 revisiones solo y
  quedó `healthy` en ~10 s. Lo público respondió 200 y lo privado 401 sin clave y 200 con ella. `tools/list` del MCP
  dentro del contenedor devolvió `buscar` y `preguntar`. Contenedores, red e imagen de prueba borrados.
- **Prueba real con Ollama** (`bge-m3` + `llama3.2:3b`, Postgres y Redis desechables, usuario público con login
  creado por la CLI), con un documento real del corpus (`Manejo cultivo integrado maracuya.txt`, 8 trozos en 24 s):
  1. Sin clave: 401.
  2. Antes de publicar, y con la colección pública pero la licencia sin verificar: búsqueda vacía.
  3. Con licencia (marcada «PRUEBA-NO-VEREDICTO», en la base desechable): 5 fragmentos.
  4. Un agente con el `Client` oficial del SDK por HTTP listó las dos tools de solo lectura y buscó con cita. La
     colección privada respondió `404: El espacio «personal» no existe`.
  5. `preguntar` tardó 114 s y respondió «2.5 a 3 centímetros [2]». **La cita es correcta, la unidad no**: la fuente
     dice «una distancia de entre 2.5 a 3» sin unidad, y el modelo de 3B le agregó «centímetros».

## Lo que se encontró por el camino

1. **Una política RLS no puede consultar su propia tabla** (recursión infinita): la de `documento` mira la colección
   y la de `trozo`, documento + colección.
2. **`role=` en la conexión se deshace** (corregido el 2026-11-16 al probarlo: no con `RESET ROLE`, que vuelve al
   rol de arranque, sino con `SET ROLE` al dueño, porque la sesión es suya). Por eso producción usa un usuario con
   login miembro del grupo, y la API no arranca sin él (G6).
3. **El build encontró lo que el test no**: la precarga fallaba dentro de la imagen porque los settings exigen
   `DATABASE_URL` y en el build no hay `.env`. Se le pasa un valor de relleno solo a ese paso.
4. **El worker heredaba el HEALTHCHECK HTTP de la imagen** y habría quedado `unhealthy` para siempre: se desactiva en
   compose.
5. **D1 rompía el archivo vacío** (división por cero en la detección de texto, porque miraba antes de detectar). Se
   corrigió con una función `_es_pdf` común.
6. **El 503 público por Redis caído decía `127.0.0.1:1`**: el detalle va al log.
7. **El SDK de MCP oculta las excepciones** («Error executing tool»): los errores de dominio salen como `ToolError`
   con su código.
8. **El session manager del MCP corre una vez por instancia**: los tests levantan un uvicorn real por módulo.
9. **FastAPI 0.163 ya no expone las rutas incluidas como `APIRoute`**: el barrido de «toda ruta pública o con
   clave» se hace sobre el OpenAPI, que es el contrato.

## Correcciones de la auditoría de seguridad (parte G, 2026-11-16)

`docs/backlog/AUDITORIA_FASE_4_2026-11-16.md`: los 13 puntos cerrados, cada uno con un test en
`tests/test_auditoria_fase4.py` (36 tests) o en el archivo del área. G6, G7, G8 y G13 se probaron contra Postgres
real con roles reales (testcontainers). Para G8, un segundo Postgres corre los scripts de `docker/initdb` y la app
migra como un dueño sin SUPERUSER. Rojo antes del arreglo: al escribir el test o por mutación (18 mutaciones: 17 rojas
y 1 equivalente por diseño, el `statement_timeout` quitado de una sola de sus dos capas; todas revertidas,
`grep MUTACION` = 0, sin `.respaldo` sueltos). `make check` después: ruff
`All checks passed!`, pyright `0 errors`, pytest **327 passed, 7 skipped** (eran 285).

| Punto | Arreglo |
|---|---|
| G1 | Middleware ASGI `ExigirClaveAntesDelCuerpo`: sin clave, 401 sin leer un byte (antes se leían los 12,5 MB del test y respondía 400). `LimiteDeCuerpo` cuenta los bytes de un cuerpo sin `Content-Length` y corta con 413; tope de 16 KB para `/api/publico` y `/mcp` |
| G2 | Cuota diaria por IP (20 respuestas) antes de la global; las cuotas diarias se gastan después de validar el alcance (un 404 o un 422 no gasta) |
| G3 | Tope diario global de búsquedas (10.000) y por IP (500); IPv6 agrupada por /64 |
| G4 | `CuposLLM`: 2 respuestas con LLM a la vez; la siguiente, 503 al instante y sin gastar cuota |
| G5 | Delimitadores con una marca aleatoria por petición (`<fragmento-<16 hex>>`): ninguna variante escrita en un documento o en la pregunta (`< /fragmento>`, `＜/fragmento＞`, mayúsculas…) es el cierre verdadero |
| G6 | Sin `DATABASE_URL_PUBLICA` la API no arranca, salvo `PERMITIR_PUBLICO_SIN_USUARIO=true`, que avisa en el log. El engine público se crea perezoso, así Alembic y las CLI no lo necesitan. Compose arma la URL con `PUBLICO_DB_PASSWORD` y `docker/arrancar-api.sh` crea el usuario después de migrar |
| G7 | La CLI se niega si el usuario es el dueño o un rol existente con SUPERUSER/BYPASSRLS, y fija `NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION` en cada corrida. Al arrancar, la API verifica eso mismo y la pertenencia al grupo |
| G8 | Producción: `docker/initdb/02-usuario-app.sh` crea `biblioteca` (dueño sin SUPERUSER, con CREATEROLE) cuando hay `APP_DB_PASSWORD`; la API y el worker migran y corren con él. `POSTGRES_PASSWORD` es obligatoria |
| G9 | El 502 de lo público dice «Un servicio externo no respondió…»; el detalle va al log. Con clave se sigue viendo |
| G10 | `API_KEY` con al menos 32 caracteres, o la app no arranca (vacía sigue cerrando lo privado con 503) |
| G11 | Redes en producción: `datos` (interna: api, worker, db, redis), `salida` (api, worker), `borde` (solo `cloudflared` y api) |
| G12 | MCP: el límite cuenta por la IP real (falla si fuera siempre «desconocida») y comparte contador con REST. RLS: las tres columnas no concedidas y `SELECT *`. Test de cuerpo grande sin clave (G1) |
| G13 | Migración `7e3a9c2b5d14`: RLS sin políticas en `extraccion` y `trabajo` (un `GRANT` equivocado no expone filas, probado) y `CHECK` que impide publicar una colección con paquete (más 422 en la API). `statement_timeout` de 5 s en la conexión pública y en el rol. Al anónimo, «La biblioteca se está actualizando», sin modelos ni comando |

Encontrado al corregir:

1. **Mi primer test de G1 no medía nada para lo público**: el `TestClient` lee todo el cuerpo en la primera llamada
   a `receive`, y el `JSONResponse` de Starlette drena el `receive` original para escuchar la desconexión. Las
   respuestas tempranas usan un `receive` ya desconectado, y cuánto se lee se mide en ASGI directo con un `receive`
   perezoso (además de la prueba por el servidor real).
2. **Un test que no puede fallar se cuelga**: la primera versión del test de lectura entregaba bloques sin fin y, con
   la mutación, la app leía para siempre. El harness quedó con un tope de 300 s por mutación, y el cuerpo falso,
   finito.
3. **`RESET ROLE` no escapa del `role=` de la conexión; `SET ROLE` al dueño sí** (ver arriba). El test lo demuestra.
4. **`statement_timeout` tiene dos capas a propósito** (conexión y rol): quitar una sola sobrevive; quitar las dos,
   rojo.
5. **`REASSIGN OWNED BY postgres` no sirve** para pasar un volumen existente al dueño sin SUPERUSER (Postgres no deja
   traspasar los objetos del sistema): `DESPLIEGUE_PUBLICO.md` usa `pg_dump --no-owner` y restaurar (sin probar).

## Archivos por importancia

1. `alembic/versions/20261116_1200_5b7c1e9d4a20_servicio_publico_flags_y_rls.py`: rol, permisos por columna,
   políticas, `agricultura` pública.
2. `app/config/database.py` (`_engine_publico`, `get_db_publico`), `app/cli/usuario_publico.py`.
3. `app/common/auth.py`, `main.py` (grupo privado, router público, MCP montado al final con su lifespan).
4. `app/services/pregunta.py` (B5, espacio opcional, `solo_publico`), `app/services/publico.py`,
   `app/routers/publico.py`.
5. `app/providers/limites.py`, `app/mcp_publico.py`.
6. `app/services/deteccion.py` (D1), `app/routers/trabajos.py` (F4), `app/services/enrutamiento.py` (F1).
7. `Dockerfile`, `docker/arrancar-api.sh`, `docker-compose.yml` (D6, worker), `docker-compose.prod.yml`.
8. Tests: `test_rls.py`, `test_auth.py`, `test_publico.py`, `test_mcp.py`, `test_redis_con_clave.py`,
   `test_auditorias_en_fase4.py`, `test_contenedor.py`.
9. Parte G: `app/common/limite_cuerpo.py` y `app/common/auth.py` (G1), `app/common/rutas.py`,
   `app/config/database.py` (G6/G7), `app/cli/usuario_publico.py` (G7), `app/providers/limites.py` (G2–G4),
   `app/services/publico.py`, `app/services/pregunta.py` (G5, G13), `app/common/errors.py` (G9),
   `app/config/settings.py` (G10), migración `7e3a9c2b5d14` (G13), `docker/initdb/02-usuario-app.sh` y
   `docker-compose.prod.yml` (G8, G11), `tests/test_auditoria_fase4.py`.

## Para la sesión supervisora

- **Compose**: la API migra al arrancar (`docker compose up --build -d` aplica `a256760ec6d6` y `5b7c1e9d4a20`).
  Redis exige `REDIS_PASSWORD`: se agregó al `.env` local, junto con `REDIS_URL` con clave y `API_KEY`, todos
  generados al azar y sin imprimirse. El `.env` estaba en 664 con secretos adentro: quedó en 600.
- **La base de compose tenía datos de una corrida anterior**: al migrar, `agricultura` queda pública y sus documentos
  ocultos (licencia sin verificar).
- Dependencia nueva: `mcp>=2.3` (`uv add`, pedida por la orden (d)). Los tests usan `httpx2`, que trae `mcp`.
- **Tras la parte G**: migración nueva `7e3a9c2b5d14` (la aplica la API al arrancar). Compose exige además
  `PUBLICO_DB_PASSWORD`; se agregó al `.env` local junto con `DATABASE_URL_PUBLICA` para correr fuera de Docker
  (generadas al azar, sin imprimirse). La API crea `biblioteca_web` sola al arrancar en compose; fuera de Docker,
  `uv run python -m app.cli.usuario_publico` una vez.

## Decisiones tomadas sin Freddy

1. **Lo privado incluye leer**: todo `/api` salvo `/api/publico` pide la clave (si no, `sobre-mi` se leía sin ella).
2. **«Rol restringido para agentes» = el mismo rol público**: el MCP es público (DECISION_SERVICIO_PUBLICO §2). No se
   creó un rol aparte que nada usara.
3. **Doble filtro**: el RLS es la garantía y las consultas públicas además filtran por `publica` y
   `licencia_verificada`, por si una ruta pública recibiera alguna vez la sesión del dueño (hay test).
4. **Lo pesado se rechaza con 413 y no se encola en silencio**: cada endpoint tiene una sola forma de respuesta.
5. **La búsqueda pública usa la misma distancia máxima que la respuesta**: sin fragmento relevante, lista vacía.
6. **Una colección privada es 404 para lo público**, igual que una inexistente.
7. **La clasificación de licencias es una propuesta por reglas**, nunca un veredicto: toda licencia queda sin
   verificar.

## Abierto

- 4.8, completa (ver `docs/DESPLIEGUE_PUBLICO.md`).
- Veredicto de licencias: 51 de 89 sin ninguna declaración, aunque se leyeron enteros; 10 «derechos reservados»;
  10 «reproducción citando la fuente»; 10 Creative Commons; 1 FAO no comercial; 7 solo `©`.
- Términos de MiniMax para la respuesta pública redactada. Sin ellos: `LIMITE_RESPUESTAS_DIARIAS=0`.
- `/docs` queda visible en producción (documenta los dos grupos). ¿Se oculta?

## Preguntas para Freddy

1. Las cuatro de `LICENCIAS_AGRICULTURA_2026-11-16.md` (citar la fuente, derechos reservados, no comercial, sin
   declaración).
2. ¿Dominio y túnel para la 4.8? ¿Se publica `/docs`?
3. ¿Los límites por defecto (30 búsquedas y 5 respuestas por minuto por IP, 200 respuestas al día) sirven?
