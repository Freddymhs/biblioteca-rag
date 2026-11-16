# Informe FASE_2 — INGESTA COMPLETA (3/4 + 4/4 sumadas; 2.3 bloqueada)

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Sin git (lo hace la sesión supervisora).
Auditada antes del commit (`AUDITORIA_FASE_2_2026-11-16.md`); la parte C quedó corregida (ver abajo).

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 2.1 Visión | `VISION_PROVIDER` (Ollama `moondream`, o `ninguno`). Páginas en blanco detectadas por tinta y descartadas antes del modelo; las con contenido se describen y quedan como trozos `origen=vision`. La cita y el prompt lo dicen |
| 2.2 Segundo plano | Redis + arq: `POST …/lotes` (202, hasta 1 GB) y `GET /api/trabajos/{id}`; worker con un trabajo por archivo, contadores atómicos, estado derivado |
| 2.3 `sobre-mi` | **BLOQUEADA** (falta `RESUME_API_URL` y el visto bueno de Freddy). Hecho: conector (contrato leído del código de la API), sincronización con altas/cambios/bajas, trabajo en segundo plano, endpoint y CLI |
| 2.4 Re-embed | `app.cli.reembeber` (y `--retrocear` desde el DoclingDocument guardado en `documento.estructura`); un documento por transacción |
| 2.B4 | Candado: Docling no corre en paralelo entre hilos |
| 2.B2 | 409 con el comando a correr cuando la colección está embebida con otro modelo (antes: «no lo sé» falso) |
| 2.B3 | Medido con `scripts/medir_hnsw.py`; ver «Decisiones» |
| 2.D | Servicio `ollama` en compose (perfil `ollama`, sin puertos), con los modelos del host en solo lectura o volumen propio |

Criterios: «carpeta sin bloquear» y «re-embed no mezcla modelos» cerrados. «Páginas sin texto de
`agricultura` buscables» abierto: el camino está probado con PDF reales, falta la ingesta completa.

## Cómo se verificó

- `make check` → ruff `All checks passed!` (111 archivos), pyright `0 errors`, pytest **165 passed, 7 skipped**
  (las 7 de oro necesitan API viva). Al empezar la fase eran 110; 140 antes de la auditoría.
- Rojo a propósito (mutación, revertida y comprobada con `grep MUTACION` = 0): sin candado → 3 conversiones a la vez;
  sin aviso B2 → el test del 409 falla; el worker sin borrar copias y el lote sin limpiar al caer Redis → 2 fallan;
  la sincronización sin bajas → falla.
- Visión con modelos reales: `Villagomez…pdf` (portada descrita en 18 s), `FAO-Fertilizer…Bulletin16.pdf`
  (página 21 en blanco descartada, sin llamar al modelo).
- Redis real (testcontainers) + worker arq en modo burst: 2 archivos encolados por la API, procesados.
- **Dentro de Docker** (`--profile ollama`, modelos del host en solo lectura): subida síncrona con visión
  (31 trozos), lote de 2 PDF por el worker (`terminado 2/2`, 32 trozos) y pregunta respondida
  «6,2 mm/día [1]» citando `NR40749.pdf` página 3. Las 4 migraciones nuevas se aplicaron a la base de
  compose con datos (`1e22705b6540 (head)`).

## Lo que se encontró y corrigió por el camino

1. **Una página con solo una figura contaba como «con texto»** (`PictureItem` con página): nunca llegaba
   a la visión. Responde la duda «no verificada» de la auditoría.
2. **moondream inventa contenido en páginas en blanco** («franjas grises»): de ahí el filtro por tinta,
   calibrado con el corpus (blanco = 0,0000; con contenido ≥ 0,04).
3. **`alembic/env.py` copiaba el `.env` completo al entorno del proceso** (`load_dotenv`): pisaba la
   configuración de quien lo importara; los tests dependían de la máquina. Ahora toma `settings.DATABASE_URL`.
4. **`add_column` con Enum no crea el tipo en Postgres** (autogenerate): creado y borrado a mano en la migración.
5. **La imagen `ollama:latest` migra los manifiestos al arrancar** y falla con modelos en solo lectura:
   fijada a la versión del host (0.34.0).

## Corregido tras la auditoría (parte C, 2026-11-16)

Cada punto con un test que falló sin el arreglo; donde el primer rojo fue un import, además una mutación
que volvió a ponerlo rojo (y se revirtió: `grep MUTACION` = 0).

| Punto | Arreglo | Test |
|---|---|---|
| C1 | fuente con 0 registros y colección con documentos → `ErrorConector`; vaciar exige `permitir_vaciar` (API y `--permitir-vaciar`) | `test_fuente_vacia_con_documentos_es_error_y_no_borra_nada`, `test_vaciar_…` |
| C2 | el conector desambigua homónimos con `position`/`startDate`…; ids repetidos → `ErrorConector`; una sola clasificación: `SIN_CAMBIOS` propio (columna `trabajo.sin_cambios`) y `DUPLICADO` igual en resumen y trabajo | `test_dos_cargos_…`, `test_ids_repetidos_…`, `test_una_sola_clasificacion_…` |
| C3 | **medido con Redis real** (abajo); barrido cron en el worker que cierra como error los trabajos vencidos sin tareas vivas en Redis (ids de tarea deterministas) y borra su carpeta; cabecera del worker corregida | `test_el_barrido_cierra_solo_los_trabajos_sin_tareas_vivas_en_redis` (Redis real) |
| C4 | toda excepción en `procesar_archivo` se registra y cuenta como ERROR (en una transacción aparte) | `test_copia_que_no_existe_cuenta_como_error_…` |
| C5 | `_guardar_copias` cuenta bytes: tope por archivo y por lote (413); docstring de `limite_cuerpo.py` corregido | `test_lote_que_supera_el_tope_al_copiar_…` (2 casos) |
| C6 | la cola se verifica antes de crear el trabajo; cualquier falla desde su creación lo descarta con su carpeta | `test_si_la_cola_no_responde_…`, `test_si_falla_la_copia_…` |
| C7 | la ruta de Redis se valida bajo `INGESTA_TEMPORAL` (fuera: error, no se lee ni se borra); tamaño por `stat` antes de leer | `test_ruta_fuera_…`, `test_copia_demasiado_grande_…` |
| C8 | total y bajas de la sincronización en un solo UPDATE al final | `test_la_sincronizacion_no_se_ve_terminada_…` |
| C9 | el contador va en la transacción del documento (`al_guardar`) | `test_si_falla_el_contador_tampoco_queda_el_documento` |
| C10 | timeout en el cliente de Ollama para visión, LLM y embeddings (los tres colgaban) | `tests/test_timeouts_ollama.py`: servidor que acepta y no responde; sin arreglo, cortado a los 30 s |
| C11 | Redis con AOF en volumen | `test_redis_persiste_la_cola_al_recrearse`; además en Docker: una clave sobrevive a `--force-recreate` |
| C12 | nombres de funciones de arq en `constantes.py`, registradas con nombre; el router ya no importa el worker | `test_el_router_no_importa_el_worker`, `test_las_funciones_de_arq_…` |
| C13 | comentarios de autogenerate fuera; `python-dotenv` quitado; helpers de tests con tipo | `tests/test_restos.py` (estático, con denominador) |

### Medición de arq (C3), con Redis real (testcontainers)

| Caso | Qué hace arq |
|---|---|
| El worker muere a mitad (`SIGKILL`), `max_tries=1` | la tarea queda `in_progress`; ~20 s después (vence `job_timeout`) otro worker la marca `max 1 retries exceeded` **sin volver a correrla** |
| Igual, `max_tries=2` | la vuelve a correr (`job_try=2`) |
| La tarea excede `job_timeout`, `max_tries=2` | **no** la reintenta (`TimeoutError`, `job_try=1`) |

Se quedó en `max_tries=1`: con 2, un archivo guardado y contado antes de la muerte se contaría dos
veces. Lo que una muerte deja a medias lo cierra el barrido.

### Encontrado al corregir

- **C9 escondía un defecto real**: `db.add()` solo no abre transacción; si el contador fallaba, el
  `rollback` no descartaba el documento pendiente y el siguiente autoflush de la sesión lo insertaba
  (guardado *y* contado como error). `_guardar` ahora hace `flush` antes y revierte ante cualquier excepción.
- El test de dependencias no usadas buscaba texto y pasaba por un comentario: ahora lee los imports por AST.
- Los tests comparten un Redis por sesión: cada uno vacía la base al usarla (un trabajo de prueba quedó
  encolado y lo tomó el worker de otro test).

## Archivos por importancia

1. `app/services/vision.py` — `indexar_paginas_sin_texto`, `_en_blanco` (umbral de tinta), páginas que no rompen la ingesta.
2. `app/worker.py` — `procesar_archivo`, `procesar_sincronizacion`, `cerrar_con_error`; `max_jobs=1`, `max_tries=1`.
3. `app/routers/trabajos.py` — lotes (copias en disco, limpieza si Redis cae) y sincronizaciones (valida el conector antes del trabajo).
4. `app/services/sincronizacion.py` y `app/conectores/resume.py` — `Cambio`, reemplazo atómico, contrato de la API.
5. `app/services/reembebido.py` y `app/services/pregunta.py` (`_avisar_si_esta_embebida_con_otro_modelo`).
6. `app/services/extraccion.py` — candado, `estructura`, `trocear_estructura`, `PictureItem`.
7. `docker-compose.yml` y `Dockerfile` — `x-app`, worker, redis, `ollama` con perfil, volúmenes `ingesta` y `modelos_hf`.
8. Migraciones `3467fd377bbf`, `8d1f2a9c7b31`, `3dc27ea57217`, `1e22705b6540`; `alembic/env.py`.
9. `scripts/medir_hnsw.py` y `docs/decisions/DECISION_HNSW_FILTROS.md`.
10. `docs/flows.md` (21 cuerpos literales), `README.md`, `.env.example`, `tests/` (9 archivos nuevos).

## Pendiente de aplicar en la base de compose

La migración `a2eea29f3917` (`trabajo.sin_cambios`) es nueva: `docker compose exec api alembic upgrade head`
(la corre la sesión supervisora después del commit, como las anteriores).

## Tareas bloqueadas y abiertas

- **2.3**: `RESUME_API_URL` y visto bueno para sincronizar contra la API real.
- **Criterio «páginas sin texto buscables»**: ingerir los 19 PDF afectados del corpus (horas de CPU) aquí
  o en el Mac Mini, con su visto bueno.
- **Si el plan MiniMax acepta imágenes**: sin verificar (no se usa su llave).

## Decisiones tomadas sin Freddy

1. **Visión por defecto `ollama`** (`moondream`). Si Ollama no está, cada página queda sin indexar y se
   registra; la ingesta no falla. Prompt «Describe this image.»: el único que no devolvió vacío en páginas con contenido.
2. **Un trabajo de arq por archivo**, `max_jobs=1` y sin reintentos: el PDF más pesado tarda minutos; un
   reintento ciego sumaría dos veces al contador.
3. **Estado del trabajo derivado de contadores**, no guardado. Una sincronización que falla entera
   termina con `errores: 1` y el motivo (no queda «pendiente» para siempre).
4. **B3: no se aplica `hnsw.iterative_scan`** — medido, no corrige el caso con JOIN. Corrección de esquema
   propuesta en el ADR (desnormalizar `espacio_id`/`coleccion_id` en `trozo` o índices parciales): decide Freddy.
5. **El conector convierte cada elemento del resume en un registro** con id `sección:nombre` y texto con
   claves ordenadas (el hash no cambia si la fuente reordena).
6. **Dependencias declaradas** que se usaban sin declarar (auditoría B7, en parte): `anthropic`, `ollama`,
   `pillow`, `pypdfium2`; nueva: `arq`.

## Preguntas para Freddy

1. ¿URL de la API de resume y visto bueno para la primera sincronización de `sobre-mi`?
2. ¿Corro la ingesta completa de `agricultura` (89 documentos, con visión) aquí o en el Mac Mini?
3. B3: ¿aplico la corrección de esquema (filtro en `trozo`) ahora o cuando el corpus completo lo pida?
