# Informe FASE_5 — OBSERVABILIDAD (2/2)

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Sin git (lo hace la sesión supervisora).

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 5.1 Trazas por pregunta | OpenTelemetry (SDK 1.45) con spans manuales, exportados por OTLP/HTTP a **Jaeger 2.23.0 local** (perfil `trazas` de compose, en memoria, interfaz solo en `127.0.0.1:16686`; sin cuenta ni llave). Toda respuesta trae `X-Traza-Id`. Etapas: `preguntar`/`buscar_publico` → `embeber_pregunta` → `buscar_trozos` → `redactar`, y `clasificar`/`calcular_sql` en un paquete. Cada una con su latencia, los trozos candidatos (con su distancia) y usados, y el proveedor. El MCP cuelga de la traza de su petición HTTP |
| 5.2 Uso público | Contadores diarios en Redis, sin IPs: búsquedas y respuestas **servidas** (un 404 o 422 no cuenta) y 429 emitidos por tipo de uso, retenidos 90 días. Los escribe el mismo `Limitador` (REST y MCP juntos). Se leen con `GET /api/uso?dias=N`, que exige la clave |

Criterio: «para cualquier respuesta se ve qué trozos usó y cuánto tardó cada etapa», cerrado con tests y con la
prueba real en Jaeger.

## Privacidad (nota (b); ver también I1 e I2 más abajo)

- Ninguna traza guarda el texto de una pregunta ni una IP; de la pregunta, solo el largo. Espacio y colección se
  anotan después de validarlos contra el catálogo, así nunca son texto libre de un visitante.
- El span HTTP se nombra con la ruta **sin query**. No se usa la auto-instrumentación HTTP.
- **Hallazgo:** FastAPI 0.163 trae su propia instrumentación OpenTelemetry, encendida por defecto, y su span HTTP
  guarda `url.query`. En `GET /api/publico/buscar?q=…` eso es la pregunta. El test de privacidad lo agarró antes de
  instrumentar nada (`url.query: 'q=secreto-xyz+olivo'`). Quedó apagada entera:
  `FastAPI(telemetry={"tracing": False, …, "auto_configure": False})`.
- Los contadores de 5.2 son solo números por día.

## Cómo se verificó

- `make check` → ruff `All checks passed!`, pyright `0 errors`, pytest **338 passed, 7 skipped** (eran 327).
- Tests (`tests/test_trazas.py`, 5):
  - Una respuesta privada trae su traza con las 4 etapas, todas con duración; los trozos usados son los del
    documento citado, y los candidatos con sus distancias.
  - Privacidad: una pregunta y una búsqueda públicas con un texto y una IP marcados (IP confiada vía
    `CF-Connecting-IP`). Ninguno aparece en nombres, atributos ni eventos de los ≥ 6 spans.
  - La búsqueda pública dice qué trozos devolvió.
  - Un cálculo traza la decisión, la herramienta y su trozo.
  - El MCP comparte la traza de su petición.
- Tests (`tests/test_uso.py`, 4):
  - Cuenta 2 búsquedas, 1 respuesta y 1 rechazo 429 de respuesta, y no cuenta el 404.
  - El MCP cuenta igual que REST.
  - Sin clave, 401; `/api/publico/uso` no existe.
  - Un día por fila, el máximo de 90 días y la vida de las claves en Redis.
- Compose (`tests/test_contenedor.py`): Jaeger va en un perfil, con la imagen fijada y publicado solo en
  `127.0.0.1`. En producción no publica nada y queda en la red interna `datos`.
- **Rojo a propósito** (11 mutaciones, 11 rojas, revertidas, sin `.respaldo` sueltos): telemetría nativa encendida,
  query en el nombre del span, texto de la pregunta en un atributo, MCP fuera de la traza, sin candidatos, sin id
  de trozo, sin proveedor, sin contar consultas, sin contar 429, y `/api/uso` fuera del grupo privado.
  - Esa última no la ve `test_uso`, porque el middleware de G1 sigue pidiendo la clave a toda ruta privada (es la
    primera barrera). La ve el barrido del OpenAPI de `test_auth.py`.
- **Procesos (nota (d))**: el harness corre cada `pytest` en su propio grupo de procesos y, si pasa el tope, mata
  el grupo entero. En la FASE_4 el `timeout` mataba a `uv` y dejaba vivo al `pytest` hijo.
  - Al terminar, `ps -eo args | grep pytest` dio **0**.
  - Ojo con `pgrep -f 'python.*pytest'`: calza con la línea de comando de la propia shell que lo lanza y da falsos
    positivos; se cuenta con `ps`.
- **Prueba real** (Jaeger, Postgres y Redis desechables; `bge-m3` + `llama3.2:3b`; usuario público con login), con
  `Manejo cultivo integrado maracuya.txt`:
  - La traza de un `POST /api/publico/preguntas` llegó a Jaeger con 5 spans: HTTP 118,5 s, `preguntar` 118,4 s,
    `embeber_pregunta` 178 ms, `buscar_trozos` 13,6 ms con candidatos `[5,6,4,2,1]` y sus distancias, y `redactar`
    118,3 s (`ChatOllama:llama3.2:3b`); trozo usado `[6]`.
  - Sobre las 17 trazas de la corrida (API v3 de Jaeger), ni el texto marcado de la pregunta ni la IP aparecen.
  - `GET /api/uso` dio 1 búsqueda y 1 respuesta (el 404 no contó); sin clave, 401.
  - Contenedores borrados y uvicorn apagado.

## Lo que se encontró por el camino

1. **La instrumentación nativa de FastAPI 0.163 filtraba la pregunta** (ver Privacidad). Cualquier proveedor de
   trazas que se hubiera configurado la habría exportado.
2. **El SDK de MCP corre las tools en su propio task group**, sin el contexto de la petición. `TrazaHTTP` guarda
   el contexto en el `scope` (el mismo que recibe la tool como `Request`) y la tool lo reactiva en su hilo.
3. **El primer test del MCP tomaba el `POST /mcp` equivocado**: el cliente hace tres (`initialize`, notificación,
   `tools/call`).
4. **`TrazaHTTP` tenía que ser el middleware más externo**: por dentro de `LimiteDeCuerpo`, un 413 no tenía span.
5. **La API de búsqueda de Jaeger v2 está en `/api/v3/traces`**. La de v1 (`/api/traces?service=`) da 404; la de
   una traza por id sigue en `/api/traces/{id}`.

## Correcciones de la auditoría (parte I, 2026-11-16)

`docs/backlog/AUDITORIA_FASE_5_2026-11-16.md`: los 12 puntos cerrados. Cada uno tiene un test que estuvo en rojo
antes del arreglo: al escribirlo o rompiendo el arreglo a propósito. Están en `tests/test_auditoria_fase5.py` (14
tests), `tests/test_trazas.py`, `tests/test_contenedor.py` y `tests/test_sin_literales.py`. `make check` después:
ruff `All checks passed!`, pyright `0 errors`, pytest **357 passed, 7 skipped** (eran 338).

| Punto | Arreglo |
|---|---|
| I1 (crítico) | `etapa` y `TrazaHTTP` abren el span con `record_exception=False` y `set_status_on_exception=False`; ante un error, solo `error.type` y el estado ERROR sin descripción. `hide_parameters=True` en los tres `create_engine`. **Probado contra Postgres real**: un vector de otra dimensión hace fallar la consulta de pgvector (`DataError`, 500); antes el SQL y el vector marcado salían en el evento de la excepción, ahora no aparecen en nombres, atributos, eventos ni `status.description` |
| I2 | **Comprobado en el SDK instalado** (`mcp` 2.3.0, `server/lowlevel/server.py:451`): `Server.middleware` arranca con un `OpenTelemetryMiddleware` que nombra el span `tools/call <nombre del cliente>`, lo copia a `gen_ai.tool.name`, toma `_meta.traceparent` como padre y, ante un error inesperado, guarda `str(e)` y la pila. Arreglo en dos capas: se quita de `servidor.middleware` (el SDK lo documenta como la forma de salir) y `SoloDeLaApp` exporta solo spans del trazador `biblioteca-rag` |
| I3 | `_registrar` solo anota en el log si Redis falla: la consulta válida sale 200 y el 429 sigue siendo 429 |
| I4 | `contar_servida` se llama al final de `buscar_publico` y `preguntar_publico`: un 502 del proveedor no cuenta. El esquema y `docs/flows.md` dicen «respondidas» |
| I5 | El span HTTP se nombra con la plantilla de la ruta (más el prefijo de `include_router`, recuperado con la regex de la ruta); el MCP, `/mcp`; cualquier otra, `(sin ruta)` |
| I6 | `clasificar` anota la herramienta solo si es una del paquete (la validada) |
| I7 | Producción: la interfaz de Jaeger en `127.0.0.1:16686` del anfitrión, por una red `panel` que no comparte con nadie (`datos` es interna y no puede publicar) |
| I8 | Desarrollo: Jaeger publica también `127.0.0.1:4318` (OTLP), como ya decía `.env.example` |
| I9 | Etapa propia `describir_imagen` (`invocar` común a redactar y a la visión). El docstring del worker deja escrito que no emite trazas |
| I10 | A `constantes.py`: `SEGUNDOS_POR_DIA` (una vez), `AtributoTraza.CODIGO_HTTP` y `TIPO_ERROR`, `CLAVE_CONTEXTO_TRAZA`, `ESPERA_VACIADO_TRAZAS_MS`, `ContadorUso` (`servidas`/`rechazadas`, ya no `"429"`) y `DIAS_USO_POR_DEFECTO`. Chequeo estático en `test_sin_literales.py` |
| I11 | `langsmith.configure(enabled=False)` al cargar `app/providers/llm.py` (el interruptor global le gana al entorno), y `LANGSMITH_TRACING`/`LANGCHAIN_TRACING_V2` en `"false"` en el entorno de compose |
| I12 | El barrido de privacidad revisa también `status.description` y nombres de eventos; hay tests con excepciones forzadas en cada etapa, del camino MCP con un nombre de tool marcado y `_meta.traceparent`, y de un 401 y un 413 |

Rojo a propósito, con el harness que mata el grupo de procesos entero: 11 mutaciones, 10 rojas. La que sobrevive es
volver a poner el middleware del SDK de MCP, porque el filtro igual descarta sus spans; quitando las dos capas a la
vez, rojo. Quitar solo el filtro también da rojo: el cliente MCP de los tests emite spans `MCP send …` con el
proveedor global en el mismo proceso, y el filtro también los deja fuera. Al terminar: 0 procesos `pytest` vivos
(chequeo que mira solo procesos de python, probado una vez con un proceso falso que sí detectó) y sin `.respaldo`.

Encontrado al corregir:

1. **LangSmith cachea el entorno** (`lru_cache` en `get_env_var`): poner `LANGSMITH_TRACING=false` después de la
   primera consulta no lo apaga. Por eso `langsmith.configure(enabled=False)`, que fija el interruptor global, y el
   test vacía ese caché (si no, no podría fallar).
2. **FastAPI 0.163 guarda en la ruta la plantilla sin el prefijo de `include_router`**: el `/api` se recupera con
   la regex de la ruta.
3. **El conteo de procesos con `pgrep -f`/`grep pytest` daba falsos positivos** (la propia shell): el chequeo nuevo
   mira solo procesos de python.

## Archivos por importancia

1. `app/observabilidad.py` (nuevo): `TrazaHTTP`, `etapa`, `anotar`, `contexto_de`/`dentro_de`, `configurar_trazas`.
2. `main.py`: la telemetría nativa apagada, `TrazaHTTP` como middleware más externo, `configurar_trazas` en el
   lifespan y el router `uso` en el grupo privado.
3. `app/services/pregunta.py` (etapas `preguntar` y `buscar_trozos`, `Cita.trozo_id`, `ids_de_trozos`,
   `anotar_alcance`), `app/services/publico.py` (`buscar_publico`) y `app/services/enrutamiento.py` (`clasificar`,
   `calcular_sql`).
4. `app/providers/embeddings.py` (`embeber_pregunta`) y `app/providers/llm.py` (`redactar`, `nombre_del_llm`).
5. `app/mcp_publico.py`: `_ejecutar` dentro de la traza y `_contexto`.
6. `app/providers/limites.py` (`_registrar`, `leer_uso`, `UsoDelDia`, `_clave_uso`), `app/routers/uso.py` y
   `app/schemas/uso.py` (nuevos).
7. `app/config/constantes.py` (`EtapaTraza`, `AtributoTraza`, `AlcanceTraza`, `ENCABEZADO_TRAZA`, `PREFIJO_USO`,
   `RETENCION_USO_DIAS`) y `app/config/settings.py` (`TRAZAS_OTLP_URL`).
8. `docker-compose.yml` (servicio `jaeger` en el perfil `trazas`, `TRAZAS_OTLP_URL`), `docker-compose.prod.yml` y
   `.env.example`.
9. Tests: `tests/test_trazas.py` y `tests/test_uso.py` (nuevos), `tests/conftest.py` (exportador en memoria, fixture
   `trazas`) y `tests/test_contenedor.py`.

10. Parte I: `app/observabilidad.py` (`_span_sin_mensajes`, `SoloDeLaApp`, `crear_proveedor_trazas`,
    `_plantilla`), `app/mcp_publico.py` (sin el middleware del SDK), `app/config/database.py`
    (`hide_parameters`), `app/providers/limites.py` (`contar_servida`, `_registrar`), `app/services/publico.py`,
    `app/services/enrutamiento.py`, `app/providers/llm.py` (`invocar`, LangSmith) y `app/providers/vision.py`,
    `docker-compose.yml` y `docker-compose.prod.yml`, `tests/test_auditoria_fase5.py`.

## Para la sesión supervisora

- Dependencias nuevas: `opentelemetry-sdk` y `opentelemetry-exporter-otlp-proto-http` (`uv add`, la nota (a) pide
  trazas). Sin migración nueva.
- Las trazas están apagadas por defecto: `TRAZAS_OTLP_URL` vacía en el `.env` local (no se tocó). Para verlas,
  ponerla en `http://jaeger:4318/v1/traces` y `docker compose --profile trazas up -d`.

## Decisiones tomadas sin Freddy

1. **Jaeger y no Langfuse ni Grafana**: un solo contenedor, recibe OTLP directo, sin cuenta ni llave. Langfuse
   self-hosted necesita su propia base y más servicios; Grafana necesita además Tempo. Cambiar de destino es solo
   cambiar `TRAZAS_OTLP_URL`: el código emite OTLP estándar.
2. **Spans manuales, sin auto-instrumentación**: la de FastAPI guarda la query; las demás (SQLAlchemy, httpx)
   agregarían dependencias y texto de consultas que nadie pidió.
3. **Jaeger en memoria**: las trazas se pierden al reiniciarlo. Para depurar alcanza; si hace falta historia, se le
   agrega almacenamiento después.
4. **Se cuentan las consultas servidas**, no las intentadas: un 404 o 422 no es uso. Los 429 se cuentan siempre.
5. **`GET /api/uso` va en el grupo privado**, con la misma clave que todo lo administrativo.

## Abierto

- Las bloqueadas de fases anteriores siguen igual: 1.9 (benchmark en el Mac Mini), 2.3 (sincronización real con
  `resume.json`) y 4.8 (exposición), además del veredicto de licencias (4.6) y la parte H de la auditoría de la
  FASE_4.
- En producción la interfaz de Jaeger se publica solo en `127.0.0.1:16686` del anfitrión (red `panel` propia, I7):
  se mira con `ssh -L 16686:127.0.0.1:16686`.

## Preguntas para Freddy

1. ¿Alcanza Jaeger en memoria, o se quiere historia de trazas (almacenamiento persistente)?
2. ¿Hace falta ver el uso público en algún tablero, o basta `GET /api/uso`?
