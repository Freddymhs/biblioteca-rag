# Auditoría de la FASE_3 — 2026-11-16, antes de su commit

Auditó una sesión distinta a la que escribió el código: 21 archivos leídos completos y el resto por diff.
`make check` ya pasaba (189 tests, 7 saltados). Los puntos E1, E2, E4, E5 y E8 se comprobaron después abriendo el
archivo.

Sin defectos en: SQL (ningún texto del LLM ni del usuario llega a una sentencia; las tres consultas son constantes
con parámetros enlazados y filtran por colección), clasificador (categoría o herramienta inexistente caen a búsqueda
semántica; el grafo no tiene ciclos), inyección por contenido (el documento solo entra al prompt de extracción y
nada se confirma sin un POST que se revalida) y compatibilidad de `POST /api/preguntas` (solo se agregan campos).

## E. Se corrige antes del commit

Cada punto se cierra con un test que falle sin el arreglo y `make check` en verde. Marcar la casilla al cerrarlo.

- [x] **E1 Re-trocear una colección con paquete expone lo no confirmado** — `app/services/reembebido.py`,
  `_trozos_nuevos`: con `--retrocear` se embebe el texto crudo de Docling, también el de documentos con extracción
  pendiente, y se descarta el trozo de datos confirmado. Rompe el criterio «un dato no confirmado no queda
  buscable». En colecciones con paquete no se re-trocea, y el trozo de origen `datos` se conserva siempre.
- [x] **E2 Se puede confirmar dos veces en paralelo** — `app/services/dominio.py`, `confirmar`: comprueba el estado,
  hace commit, embebe por red y vuelve a leer sin comprobar de nuevo ni bloquear la fila. Dos POST simultáneos
  pasan los dos y el segundo sobrescribe lo confirmado. Releer con bloqueo o repetir la comprobación, y responder 409.
- [x] **E3 Un cero que parece dato** — `app/services/enrutamiento.py`: la ruta de cálculo siempre responde
  `sabe=True`. Sin datos confirmados dice «Facturas confirmadas: 0.» sin citas. Sin filas, `sabe=False` y un texto
  que diga que no hay datos confirmados.
- [x] **E4 Ranking y máximo mezclan monedas** — `app/dominio/facturas.py`, `SQL_POR_EMISOR` y `SQL_MAS_ALTA`:
  ordenan por monto sin distinguir moneda (5.000 CLP queda sobre 1.000 USD). Ranking y máximo por moneda.
- [x] **E5 Subir un documento ahora exige tener un LLM configurado** — `app/routers/documentos.py`:
  `Depends(obtener_extractor)` instancia el LLM en toda subida, también a colecciones sin paquete; sin llave
  configurada responde 503 donde antes funcionaba. Resolver el extractor solo si la colección tiene paquete.
- [x] **E6 No se puede rechazar ni corregir** — `app/routers/extracciones.py` y `app/services/dominio.py`: una
  extracción confirmada con un error queda para siempre en los cálculos, y una pendiente mala no se puede descartar.
  Agregar el rechazo de una pendiente y la corrección de una confirmada (reemplaza datos y trozo en una transacción).
- [x] **E7 Montos sin límite** — `app/dominio/facturas.py`: los `Decimal` aceptan `1E+200000`; una sola fila así
  haría fallar todo cálculo de la colección. `max_digits` y `decimal_places` con constantes.
- [x] **E8 El `downgrade` deja trozos huérfanos** — migración `a256760ec6d6`: borra la tabla `extraccion` pero deja
  los trozos de origen `datos`, que el código anterior no sabe leer. Borrarlos antes de quitar la tabla.
- [x] **E9 Una sola fuente** — `'confirmada'` literal dentro del SQL de `app/dominio/facturas.py`; `"calculo"` y
  `"significado"` repetidos en cuatro sitios; `"CLP"` como valor por defecto silencioso de `moneda` (una factura sin
  moneda entra como CLP sin que nadie lo haya leído). Enum para la decisión, parámetro para el estado, y `moneda`
  obligatoria o marcada como supuesta en la propuesta.
- [x] **E10 Descripción vieja** — `app/schemas/pregunta.py`, `CitaSalida.origen`: falta el valor `datos`.
- [x] **E11 Código real sin tests** — `extraer_con_llm`, `_propuesta` y `clasificar_con_llm` solo se prueban a
  través de dobles. Tests con salidas simuladas (JSON roto, no objeto, no valida, LLM que lanza) y los casos
  negativos que faltan: dos monedas, dos colecciones con paquete (el cálculo de una no ve la otra) y cero facturas.
- [x] **E12 Aislamiento por construcción** — `app/dominio/base.py`: `{"coleccion_id": …, **argumentos}` deja que un
  campo futuro llamado `coleccion_id` pise el filtro; ponerlo al final. `app/dominio/facturas.py`, `_FACTURAS`:
  filtrar también por `paquete = 'facturas'`, para que los CAST no corran sobre extracciones de otro paquete.

## F. Abierto, no bloquea este commit

- **F1 Sin tope de citas en un cálculo**: un total sobre miles de facturas devuelve miles de citas. → FASE_4.
- **F2 El texto se trunca a 12.000 caracteres sin avisar** a quien confirma. → agregar un aviso en `errores`.
- **F3 La salida estructurada solo está medida con Ollama `llama3.2:3b`.** Con MiniMax no se probó: si falla, la
  clasificación cae a búsqueda semántica sin ruido. → probar al habilitar la llave real.
  > Sigue abierto 2026-11-16 (FASE_6, 6.5): la llave está, pero MiniMax responde 402 `insufficient balance`.
- **F4 Un lote hacia una colección con paquete responde 202 y falla archivo por archivo.** Rechazarlo de entrada.
- **F5 «Hoy» del clasificador usa la zona horaria del servidor.**
- **F6 Clientes con un enum estricto de `origen`** (`texto` | `vision`) fallarán con `datos`. Afecta al portal: está
  en `docs/flows.md`.

## No verificado por la auditoría

- Cómo responde Postgres real a `1E+200000` en un `::numeric`.
- El comportamiento de la salida estructurada con respuesta vacía en los proveedores reales.
