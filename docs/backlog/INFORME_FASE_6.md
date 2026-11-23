# Informe FASE_6 — DECISIONES DE FREDDY (7/8)

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Sin git (lo hace la sesión supervisora).
Origen: respuestas de Freddy a `PENDIENTES_FREDDY_2026-11-16.md`; cada punto respondido quedó cerrado allí con su
respuesta, quién y cuándo.

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 6.1 Título real en las citas (punto 7) | `documento.titulo`, `fuente` y `anno`, opcionales (migración `9c4d2e7f1a36`, con `GRANT` de esas columnas al rol público). Llegan por el formulario al subir y en la CLI con `--catalogo <json>` (lista de objetos con `archivo`, o mapa archivo → metadatos; una entrada inválida se rechaza nombrándola). La cita trae `titulo`, que cae al nombre del archivo, más `fuente` y `anno`. Nada de agricultura en el código; el `catalogo.json` real (89 entradas) se lee en un test que se salta si no está |
| 6.2 Sin referencia, «no lo sé» (punto 8) | Una respuesta sin ningún `[n]` válido es «no lo sé» con `citas: []` |
| 6.3 Filtros e índice HNSW (punto 9) | Medido antes y después (abajo). `trozo.espacio_id` y `coleccion_id` desnormalizados (migración `b1e6f3a9d250`, FK, btree, trigger que los completa) y búsqueda **exacta por construcción** con una CTE `MATERIALIZED`. ADR `DECISION_HNSW_FILTROS.md` reescrito con los números |
| 6.4 `/docs` en producción (punto 11) | `DOCUMENTACION_API` (por defecto `true`); `docker-compose.prod.yml` la pone en `false`: `/docs`, `/redoc` y `/openapi.json` dan 404 |
| 6.5 MiniMax real (puntos 5 y 3) | **BLOQUEADA**: ver abajo |
| 6.6 El portal consume lo público (punto 6) | `DECISION_PORTAL_CONSUME_PUBLICO.md`; en `docs/flows.md`, sección «Para quien escribe el cliente del portal», con cuerpos literales capturados de la API, tabla de errores, límites y CORS. Corregido de paso: CORS no exponía `X-Traza-Id` al navegador (ahora sí) |
| 6.7 Licencias (punto 4) | Veredicto de Freddy en la tabla: 79 «publicar», 10 «no publicar: derechos reservados». `python -m app.cli.licencias --tabla … --espacio … --coleccion …` muestra qué haría; con `--aplicar` escribe. Aplicado en `biblioteca_rag_prod` el 2026-11-22 (ver «Ingesta y licencias») |
| 6.8 Benchmark de embeddings (punto 1, sumada) | Coseno mínimo 0,999991; Ollama y Cloudflare comparten el identificador `bge-m3` (B2). Ver abajo |

## 6.3: lo que dijo la medición

`scripts/medir_hnsw.py` sobre una base desechable: los 63 trozos reales en una colección pública y 20.000 trozos
de ruido del mismo tema en otra colección privada. «Forzado» simula lo que hará el planificador con muchos datos.

- **Antes** (sin columnas): exacta 5 de 5; con el índice HNSW, 1 de 5 en lo privado y en lo público, con o sin
  `iterative_scan` (estricto, relajado y con `max_scan_tuples` en 1.000.000).
- **Desnormalizar no basta**: con el filtro en `trozo`, el índice también devuelve 1 de 5. Por eso la búsqueda pasó
  a ser exacta: el índice HNSW no puede servir esa forma de consulta.
- **Después (la app)**: 5 de 5 y recall 1,0 en todos los modos, privado y público. Latencia: 1,5 ms privada y 43 ms
  pública con 63 trozos filtrados; 134 ms privada con 20.063 trozos en el mismo espacio.
- **Índice parcial por espacio**: medido, no aplicado. Corrige los vecinos de otro espacio, pero con 20.000 trozos
  parecidos dentro del mismo espacio su recall cae a 0,2–0,6, y no sirve a lo público.
- **Hallazgo**: las cifras del ADR anterior estaban contaminadas. psycopg prepara la consulta en el servidor a
  partir de la sexta repetición y reusaba el plan de otro modo. El script ahora mide con `prepare_threshold=None`.
- Umbral para revisarlo, en el ADR: un espacio de más de unos 100.000 trozos (≈ 0,7 s por búsqueda).

## 6.5: por qué está bloqueada

La llave de MiniMax del `.env` es de plan (`sk-cp-…`) y es **válida**: una llave inventada da 401. Con ella,
`https://api.minimax.io/anthropic` responde **402 `insufficient_balance_error` «insufficient balance (1008)»** con
`MiniMax-M2.7-highspeed` (el configurado), `MiniMax-M2.7`, `MiniMax-M2.5` y `MiniMax-M2.5-highspeed`.
`MiniMax-M2` y `MiniMax-M2.1` ya no existen (404). `https://api.minimaxi.com/anthropic` rechaza la llave (401).

Medido con MiniMax: **0 preguntas de oro, 0 pruebas de punta a punta, 0 salidas estructuradas**. Nada pasó porque
nada llegó al modelo. F3 y la nota de la tarea 1.6 siguen abiertas, con esta causa anotada. Pregunta a Freddy: punto 15
de los pendientes.

La respuesta redactada pública ya está habilitada con los límites actuales; no hay ningún interruptor que la apague.
Con `LLM_PROVIDER=minimax` y sin saldo, responde 502. El `.env` local dice `LLM_PROVIDER=ollama`.

## 6.8: benchmark y decisión B2

`scripts/benchmark.py` en el ThinkPad, tres corridas:

- Coseno del mismo texto, Ollama vs Cloudflare: mínimo **0,999991** sobre 5 textos (umbral 0,99). OK.
- Control agregado al script para que el chequeo pueda fallar: textos distintos dan 0,4634 como máximo (20 pares).
  La mayor diferencia en un componente es 7,6 × 10⁻⁴.
- Embedding de una pregunta (mediana de 10): Ollama 0,20–0,25 s; Cloudflare 0,16–0,73 s. Los dos OK (máximo 1 s).

**Decisión**: comparten identificador. `MODELOS_EQUIVALENTES` mapea los dos a `bge-m3`. Solo los pares medidos:
otro modelo conserva `proveedor:modelo`. Las trazas siguen diciendo qué proveedor respondió (`quien_responde`). La
migración `c7a2d4e8f613` pasa lo ya guardado al identificador común. ADR: `DECISION_BGE_M3_IDENTIFICADOR_COMUN.md`.
No se tocó `EMBEDDINGS_PROVIDER` del `.env`. Sigue bloqueada la parte de la 1.9 en el Mac Mini.

## Cómo se verificó

- `make check` → ruff `All checks passed!`, pyright `0 errors`, pytest **384 passed, 7 skipped**. Al cerrar la FASE_5
  eran 357. Con las correcciones K y K7 (2026-11-22): **426 passed, 7 skipped**.
- Cada cambio tiene su test, escrito antes y visto en rojo. Verificados en esta sesión:
  - Los de 6.6 (`expose_headers`) y de B2: los tres de B2 fallaban antes de implementar.
  - Mutaciones sobre 6.3:
    - Quitar el ajuste de búsqueda en la versión intermedia: los tests **no** fallaban (3 pasaron).
    - Por eso el test ahora obliga al planificador a preferir cualquier índice: apaga `enable_seqscan`,
      `enable_bitmapscan` y `enable_sort`.
    - Volver a la forma que HNSW sí puede servir (`ORDER BY … LIMIT` directo): falla
      `test_63_lo_privado_encuentra_lo_de_su_coleccion_aunque_haya_vecinos_en_otra`.
- Pruebas reales: Cloudflare y Ollama (benchmark); MiniMax (402, arriba); Postgres de verdad con el rol
  `biblioteca_publico` (medición de 6.3 y tests).
- Procesos de pytest huérfanos al terminar: 0.

## Correcciones de la auditoría (K)

`AUDITORIA_FASE_6_2026-11-16.md` encontró seis puntos para corregir antes del commit. Los seis están cerrados, cada
uno con su test en `tests/test_auditoria_fase6.py`.

| Punto | Qué se cambió |
|---|---|
| K1 Citas válidas leídas como «no lo sé» | Una referencia es un corchete con números, listas o rangos: `[1, 2]`, `[1;2]`, `[ 1 ]`, `[1-3]`, `[1–3]`. Un rango se expande hasta `MAX_NUMEROS_POR_RANGO_REFERENCIA` números. Las instrucciones piden un número por corchete (`[1][2]`) |
| K2 El `LIMIT` llegaba tarde | Se ordena y se corta sobre `(id, distancia)`; solo los 5 elegidos se unen con su trozo y su documento. Medido abajo |
| K3 Comando de licencias más estricto | Un archivo repetido se rechaza nombrándolo; solo las formas conocidas del veredicto publican o no; se lee solo la tabla bajo su cabecera; una fila mal formada se rechaza nombrando la línea; sin ninguna fila que calce, o al aplicar con filas sin documento, sale con error |
| K4 Títulos en blanco | Título y fuente se recortan, y uno en blanco cuenta como ausente (la cita cae al nombre del archivo). Un carácter de control da 422 por API y un error con el nombre de la entrada en el catálogo |
| K5 Log que mentía | El arranque anuncia `/docs` solo si está abierta |
| K6 Comentario duplicado | Queda un solo comentario B5 en `pregunta.py` |

**K2 medido** (`scripts/medir_busqueda.py`, base desechable, 25.000 trozos que pasan todos el filtro, mediana de 75
búsquedas). Privada: 168 → **134 ms**. Pública: 254 → **142 ms**. Las dos versiones devuelven 5. Con el corpus real
(11.628 trozos), 53 ms. Detalle en `DECISION_HNSW_FILTROS.md`.

**Mutación** (2026-11-22): con el `pregunta.py` anterior a K, fallan los tests de K1, K2 (privada y pública) y K6
(14 de 17).

## Ingesta y licencias (hechas)

- Ingesta completa el 2026-11-16, de 14:59 a 19:17, en la base `biblioteca_rag_prod` del contenedor `db` de compose:
  89 documentos, 11.628 trozos, 158 de visión, embeddings Cloudflare (`bge-m3`), con `--catalogo` (títulos).
- Licencias aplicadas el 2026-11-22 con `python -m app.cli.licencias … --aplicar`: simulación y aplicación dieron
  89 filas, **79 verificadas, 10 sin publicar** (las de «todos los derechos reservados»).
- La base de desarrollo (`biblioteca_rag`) no se migró: sigue en la revisión de la FASE_5.

## Abierto

- 6.5 / F3 / nota 1.6: cerradas el 2026-11-23, sin LLM propio (punto 15). F3 (salida estructurada con MiniMax) no se medirá.
- 1.9: la parte del Mac Mini. 2.3, 4.8 y el punto 10 (páginas sin texto: ThinkPad o Mac Mini) siguen esperando a Freddy.
