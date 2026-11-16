# Informe FASE_3 — DOMINIO Y ENRUTAMIENTO (3/3)

Fecha: 2026-11-16 · Sesión asistida por IA, sin Freddy presente. Sin git (lo hace la sesión supervisora).

## Qué quedó hecho

| Tarea | Resultado |
|---|---|
| 3.1 Paquete de dominio | Contrato `PaqueteDominio` (esquema Pydantic, texto a embeber, herramientas SQL). Una colección declara su paquete (`coleccion.paquete`). Subir a esa colección extrae el texto (Docling), pide los datos al LLM y guarda una `extraccion` **pendiente** sin trozos. `GET /api/extracciones/{id}/formulario` entrega el JSON Schema + la propuesta + sus errores; `POST …/confirmacion` valida contra el esquema y recién ahí embebe un trozo `origen=datos` |
| 3.2 Enrutamiento | LangGraph (`clasificar → calcular | buscar`). El clasificador elige una herramienta de un **enum cerrado** del paquete y propone argumentos que valida Pydantic; el SQL es fijo y parametrizado; la respuesta de un cálculo la escribe un formateador, no el LLM. Toda decisión inválida va a la búsqueda semántica. `RespuestaSalida` informa `ruta` (`semantica`/`sql`) y `herramienta` |
| 3.3 `facturas` | Esquema (folio, fecha, emisor, RUT, receptor, moneda, neto, IVA, total, líneas) con validadores de plausibilidad; 4 herramientas: `total_facturado`, `cantidad_de_facturas`, `facturado_por_emisor`, `factura_mas_alta` |

Criterios: los dos cerrados (con tests y con la prueba real, ver abajo).

## Cómo se verificó

- `make check` → ruff `All checks passed!`, pyright `0 errors`, pytest **189 passed, 7 skipped** (eran 165).
- Rojo a propósito, por mutación (revertidas; `grep MUTACION` = 0): sin la guardia de `ingestar`, lotes y CLI
  embebían sin confirmar; confirmar con `model_construct` aceptaba fechas imposibles; el SQL sin el filtro
  `estado = 'confirmada'` contaba lo no confirmado; sin el validador de año pasaba el 1203; el borde siempre a
  semántica, los argumentos sin validar, una herramienta inexistente aceptada y el SQL sin filtro de fechas:
  cada uno pone rojo su test.
- **Prueba real con Ollama** (`llama3.2:3b` extrae y clasifica, `bge-m3` embebe, base desechable), 3 facturas
  y 4 preguntas:

| Pregunta | Ruta | Resultado |
|---|---|---|
| ¿Cuánto facturé en total? | SQL `total_facturado` | 399.000 CLP en 3 facturas, 3 citas: correcto |
| ¿Cuántas facturas tengo de marzo de 2026? | SQL `cantidad_de_facturas` (fechas 2026-03-01 a 2026-03-31) | 2: correcto |
| ¿Qué emisor me facturó más? | semántica (debió ser `facturado_por_emisor`) | acertó por casualidad |
| ¿Qué servicio prestó Podas del Sur? | semántica | «no lo sé»: el trozo de datos quedó sobre el umbral |

## Lo que se encontró por el camino

1. **La extracción del modelo chico es mala y por eso se confirma**: folio «Pc 4521» y «Yes», moneda «DOL»,
   «12-03-2026» leído como el año 1203 (válido para Python) o 205 o 2003. El validador de año (1990–2100)
   detecta los imposibles; 2003 es plausible y solo lo corrige una persona.
2. **El clasificador omitía la herramienta**: con `herramienta` opcional, `llama3.2:3b` respondía «calculo»
   sin nombrarla y todo caía a semántica (0 de 3). Con un esquema por paquete donde `herramienta` es
   obligatoria y un `enum` de sus nombres, Ollama restringe la decodificación: 2 de 3.
3. **`function_calling` falla con fechas en Ollama**; `json_schema` funciona. Se usa `json_schema`.
4. **El protocolo de nodos de LangGraph exige que el parámetro se llame `state`** (pyright lo marca si no).

## Archivos por importancia

1. `app/services/enrutamiento.py` — el grafo, `_calculo_valido` (nada sin validar llega al SQL), `_calcular`.
2. `app/dominio/base.py` y `app/dominio/facturas.py` — contrato, esquema, SQL fijo con parámetros (`strpos`, sin LIKE).
3. `app/providers/estructurado.py` — extractor y clasificador; `esquema_de_decision` (enum cerrado).
4. `app/services/ingesta.py` (`ingestar_con_paquete` y la guardia) y `app/services/dominio.py` (formulario, confirmación).
5. `app/models/extraccion.py`, `app/models/coleccion.py`, migración `a256760ec6d6` (con `ALTER TYPE … ADD VALUE 'datos'`).
6. `app/routers/extracciones.py`, `app/routers/documentos.py`, `app/routers/preguntas.py`, `app/routers/catalogo.py`.
7. `tests/test_enrutamiento.py`, `tests/test_extracciones.py`, `tests/test_paquete_facturas.py`; `docs/flows.md`, `README.md`.

## Correcciones de la auditoría (parte E, 2026-11-16)

`docs/backlog/AUDITORIA_FASE_3_2026-11-16.md`: los 12 puntos cerrados, cada uno con un test que falló
antes del arreglo (`tests/test_auditoria_fase3.py`, 20 tests; `tests/test_estructurado.py`, 9;
`tests/test_migraciones.py`, 1). Rojos: 18 por aserción y 2 que no podían correr sin la API nueva (E5,
E12), comprobados por mutación junto con E1, E2, E3 y E11 (7 mutaciones, 7 rojos, revertidas).
`make check` después: ruff `All checks passed!`, pyright `0 errors`, pytest **219 passed, 7 skipped**
(eran 189).

| Punto | Arreglo |
|---|---|
| E1 | `reembeber_coleccion(..., retrocear=True)` sobre una colección con paquete → 422; el re-embebido conserva el trozo `datos`. La CLI sobre todo el espacio las re-embebe sin re-trocear (antes la primera colección con paquete abortaba el resto) |
| E2 | `confirmar` relee la extracción con `SELECT … FOR UPDATE` después de embeber y vuelve a comprobar el estado: la segunda confirmación es 409 y no pisa la primera |
| E3 | Cálculo sin filas → `sabe: false`, «No hay facturas confirmadas.», sin citas |
| E4 | Ranking con `ROW_NUMBER() OVER (PARTITION BY moneda)` y máximo con `DISTINCT ON (moneda)` |
| E5 | `Depends(obtener_fabrica_extractor)`: el LLM se instancia solo si la colección tiene paquete |
| E6 | `POST /api/extracciones/{id}/rechazo` y `PUT /api/extracciones/{id}/confirmacion` (ver Decisiones) |
| E7 | Montos con `max_digits=15`, `decimal_places=2`; cantidad 12/3 (constantes en `facturas.py`) |
| E8 | El `downgrade` de `a256760ec6d6` borra los trozos `origen='datos'` antes de quitar la tabla |
| E9 | `TipoDecision` (enum) en lugar de `"calculo"`/`"significado"`; estado como parámetro `CAST(:estado_confirmada AS estado_extraccion)`; `moneda` obligatoria |
| E10 | `CitaSalida.origen` describe sus tres valores desde un mapa por `OrigenTrozo` (no puede quedar atrás) |
| E11 | Tests de `extraer_con_llm`, `_propuesta` y `clasificar_con_llm` (JSON roto, no objeto, no valida, LLM caído, tipo inexistente, salida incompleta) + dos monedas, dos colecciones con paquete, cero facturas |
| E12 | `ejecutar` pone `coleccion_id`, `paquete` y estado DESPUÉS de los argumentos; `_FACTURAS` filtra `e.paquete = :paquete` |

Encontrado al corregir:

1. **El clasificador aceptaba una salida incompleta como cálculo** (E11): un proveedor que devolviera
   `{"tipo": "calculo"}` como dict pasaba `Decision` (campos opcionales) y llegaba a `_calculo_valido`.
   Ahora se valida primero contra el esquema estricto del paquete; si no pasa, significado.
2. **La CLI de re-embebido** recorría todo el espacio con `--retrocear` y la guardia de E1 la habría
   cortado en la primera colección con paquete: ahora esas se re-embeben sin re-trocear, con aviso.
3. **Un `.pyc` viejo hizo pasar una mutación como si siguiera viva**: la mutación de E12 intercambia dos
   líneas (mismo tamaño) y se revirtió dentro del mismo segundo, así que Python reusó el bytecode mutado
   y el test quedó rojo con el código ya correcto. Se borraron los `__pycache__` y el harness de
   mutaciones corre ahora con `PYTHONDONTWRITEBYTECODE=1`.
4. **Un test de migración que corre `downgrade` no puede vivir dentro de la transacción del test**: se
   colgaba esperando el bloqueo de la conexión del fixture. E8 está en `tests/test_migraciones.py`, con
   datos insertados y limpiados en su propia conexión.

## Pendiente de aplicar en la base de compose

Migración `a256760ec6d6` (paquetes y extracciones): `docker compose exec api alembic upgrade head`. La
corrección E8 solo cambia su `downgrade`: sigue siendo la misma revisión, sin migración nueva.

## Decisiones tomadas sin Freddy

1. **Herramientas SQL sobre JSONB** (`extraccion.confirmados`), no una tabla por paquete: un paquete nuevo no
   necesita migración. Cada SQL filtra por colección, paquete y estado confirmado (parámetros).
2. **Colecciones con paquete solo por `POST …/documentos`**: lotes, CLI y conectores responden 422; así nada se
   indexa sin confirmar. Ir por la cola exigiría una confirmación asíncrona (pendiente si hace falta).
3. **Se embebe solo el texto de los datos confirmados** (un trozo por documento), no el texto original.
4. **La respuesta de un cálculo es determinista** (formateador del paquete), no redactada por el LLM.
5. **Se clasifica solo dentro de una colección con paquete**; una pregunta a todo el espacio va por semántica.
6. **Un cálculo sin filas es `sabe: false`** (corregido en E3): sin datos confirmados no hay dato que
   respaldar; responde «No hay facturas confirmadas.» sin citas.
7. **Rechazo y corrección (E6)**: `POST …/{id}/rechazo` borra una pendiente con su documento (el archivo
   puede volver a subirse); `PUT …/{id}/confirmacion` corrige una confirmada. Ambos 409 con el estado
   equivocado. Cuerpos literales en `docs/flows.md`.
8. **`moneda` obligatoria (E9)**: sin default. Si el LLM no la lee, la propuesta trae el error y la
   persona la completa.

## Abierto

- 1 de 3 cálculos cayó a semántica con el modelo de 3B; medir con MiniMax (sin llave) o un modelo local mayor.
- Las preguntas de significado sobre datos confirmados fallan con el umbral 0,55: el texto de datos es corto.
  Recalibrar (o embeber también el texto original confirmado) con más facturas reales.
- Con MiniMax (`ChatAnthropic`) `with_structured_output(method="json_schema")` está sin probar.

## Preguntas para Freddy

1. ¿El paquete `facturas` refleja las facturas que te interesan (chilenas: folio, RUT, neto, IVA)? ¿Otro campo?
2. ¿Confirmación asíncrona para lotes (subir muchas facturas y confirmarlas después) o basta una por una?
