# Auditoría de la FASE_5 — 2026-11-16, antes de su commit

Auditó una sesión distinta a la que escribió el código. `make check` ya pasaba (338 tests, 7 saltados). Los puntos
I1 e I2 se comprobaron después abriendo el archivo.

Sin hallazgos en: la URL con su consulta (la traza HTTP guarda la ruta sin `?q=…`, sin cabeceras, sin IP y sin la
clave), instrumentación automática (no hay ninguna instalada; la de FastAPI está apagada), ids de trozos privados en
peticiones públicas, el encabezado `X-Traza-Id`, el orden de los middlewares, la propagación del contexto entre
hilos, y los contadores (atómicos, con expiración, sin IP en sus claves, y `/api/uso` exige la clave).

## I. Se corrige antes del commit

Cada punto se cierra con un test que falle sin el arreglo y `make check` en verde. Marcar la casilla al cerrarlo.

- [x] **I1 CRÍTICO — una excepción vuelca su mensaje completo en la traza** — `app/observabilidad.py`, `etapa` y
  `TrazaHTTP`: `start_as_current_span` registra por defecto la excepción con su mensaje y su traza de pila. Un error
  de base durante una búsqueda pública exporta el SQL con sus parámetros, entre ellos el vector de la pregunta del
  visitante; lo mismo con mensajes de proveedores y de cualquier 500. Pasar `record_exception=False` y
  `set_status_on_exception=False`, y ante un error anotar solo el tipo de la excepción. `hide_parameters=True` en los
  tres `create_engine` de `app/config/database.py`. Test: lanzar una excepción con un texto marcado dentro de cada
  etapa y comprobar que no aparece en nombres, atributos, eventos ni `status.description` de ningún span.
- [x] **I2 El SDK de MCP exporta sus propios spans con texto del visitante** — el servidor MCP trae un middleware de
  OpenTelemetry activo que usa el proveedor global: el nombre de la tool que envía un anónimo (texto libre, hasta
  16 KiB) queda como nombre y atributo de span, y el cliente puede fijar el id de traza con `_meta.traceparent`.
  Quitar ese middleware o descartar sus spans con un procesador. Test con un nombre de tool marcado y un
  `_meta.traceparent`.
- [x] **I3 Un fallo del contador rompe la respuesta** — `app/providers/limites.py`, `_registrar`: si Redis falla al
  contar, una consulta válida sale como 503, y un 429 queda tapado por un 503. La métrica falla en silencio (log) y
  la respuesta sigue.
- [x] **I4 «Servidas» cuenta lo que no se sirvió** — `app/providers/limites.py` y `app/schemas/uso.py`: se cuenta al
  reservar la cuota, antes de embeber y buscar; un 502 del proveedor queda como servido. Contar al final, o llamar
  al dato por lo que es en el esquema y en `docs/flows.md`.
- [x] **I5 Nombres de span sin tope** — `app/observabilidad.py`, `TrazaHTTP`: el nombre usa la ruta cruda, y el
  montaje del MCP atiende cualquier ruta; un escáner crea un nombre distinto por cada URL. Usar la plantilla de la
  ruta resuelta, o un nombre fijo cuando no hay ruta.
- [x] **I6 Se anota la herramienta antes de validarla** — `app/services/enrutamiento.py`: `decision.herramienta` es
  texto libre del LLM. Anotarla solo si pasó la validación.
- [x] **I7 En producción no se puede abrir Jaeger** — `docker-compose.prod.yml` y `docs/backlog/INFORME_FASE_5.md`:
  la red es interna y no hay puerto; el informe dice que se mira por un túnel SSH y no hay ruta desde el anfitrión.
  Publicar la interfaz solo en `127.0.0.1` del anfitrión por una red aparte, o corregir el texto.
- [x] **I8 `.env.example` apunta a un puerto que no se publica** — indica `http://127.0.0.1:4318` para correr fuera
  de Docker, y compose solo publica el 16686. Publicar el 4318 en `127.0.0.1` en desarrollo, o quitar la frase.
- [x] **I9 La descripción de imágenes sale como «redactar»** — `app/providers/llm.py` y `app/providers/vision.py`:
  la visión reutiliza la etapa de redactar respuestas. Nombre de etapa propio. Dejar escrito que el worker no emite
  trazas.
- [x] **I10 Constantes** — `VENTANA_DIARIA_SEGUNDOS` y `SEGUNDOS_POR_DIA` repiten el mismo número; quedan fuera de
  `app/config/constantes.py` el atributo `http.response.status_code`, la clave de contexto, los sufijos del contador
  (`"429"` se confunde con el código HTTP) y los días por defecto de `/api/uso`.
- [x] **I11 Apagar LangSmith por construcción** — está instalado como dependencia de LangChain: una variable
  `LANGSMITH_TRACING` en el `.env` exportaría los prompts con la pregunta a un servicio externo. Forzarla apagada
  en el arranque y en compose.
- [x] **I12 Test de privacidad incompleto** — `tests/test_trazas.py`: no revisa `status.description`, no fuerza
  excepciones, no prueba el camino MCP con el texto en el nombre de la tool, ni un 401 o 413.

## J. Abierto, no bloquea este commit

- **J1 Jaeger sin límite de memoria** y con almacenamiento en memoria. → al desplegar.
- **J2 Sin cierre explícito del exportador**: con el colector caído, apagar el proceso tarda unos 8 s.
- **J3 Los errores de dominio (404, 422, 429) marcan la etapa como error.** Decidir si lo son.
- **J4 `/api/uso` con Redis caído** responde con un mensaje pensado para el visitante anónimo.
- **J5 Tests de contadores**: solo cubren el 429 por minuto; faltan cuota diaria por IP, tope global y MCP.

## No verificado por la auditoría

- Si la imagen de Jaeger fijada existe y dónde escucha su receptor.
- Si los mensajes de error de los proveedores reales incluyen texto de la pregunta.
- El formato exacto del error con Postgres real (se probó con SQLite; SQLAlchemy usa el mismo formato).
