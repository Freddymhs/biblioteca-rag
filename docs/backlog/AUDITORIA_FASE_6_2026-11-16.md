# Auditoría de la FASE_6 — 2026-11-16, antes de su commit

Auditó una sesión distinta a la que escribió el código. `make check` ya pasaba (384 tests, 7 saltados).

**Sin hallazgos críticos.** Comprobado:

- El rol público tiene permiso sobre las columnas nuevas, y la búsqueda pública con el rol real está probada en
  Postgres.
- Un documento no público no expone su título.
- El trigger de `trozo` sobrescribe un `espacio_id` falso.
- La cadena de migraciones es lineal, con un solo head.
- El comando de licencias solo toca la colección indicada: con la tabla real publica 79 y deja fuera exactamente
  los 10 de «todos los derechos reservados».
- El catálogo real carga sus 89 entradas.

## K. Se corrige antes del commit

- [x] **K1 Citas válidas leídas como «no lo sé»** — `app/services/pregunta.py`: solo se reconoce `[n]`. Respuestas
  con `[1, 2]`, `[1,2]`, `[ 1 ]` o `[1-3]` salen con `sabe=false` y sin citas. Aceptar listas y rangos, y pedir en
  las instrucciones un número por corchete (`[1][2]`).
- [x] **K2 Búsqueda: el `LIMIT` llega tarde** — `app/services/pregunta.py`: la consulta une los trozos completos
  (con su vector y su texto) de todos los candidatos y recién después ordena y corta en 5. Ordenar y cortar sobre
  los ids, y unir solo esos. Medir la latencia con la consulta real.
  > Medido 2026-11-22 (25.000 trozos): privada 168 → 134 ms, pública 254 → 142 ms (`DECISION_HNSW_FILTROS.md`).
- [x] **K3 Comando de licencias más estricto** — `app/services/licencias.py` y `app/cli/licencias.py`: un archivo
  repetido en la tabla gana en silencio; cualquier veredicto que empiece con «publicar» publica; una segunda tabla
  en el `.md` o una celda vacía da un error sin mensaje; el comando sale con 0 aunque no calce ninguna fila.
- [x] **K4 Títulos en blanco** — `app/schemas/documento.py`: un título o una fuente de solo espacios pasa, y la cita
  queda sin título; un carácter NUL llega a Postgres y da 500. Recortar espacios y rechazar caracteres de control.
- [x] **K5 Log que miente** — `main.py`: anuncia `/docs` aunque esté cerrado en producción.
- [x] **K6 Comentario duplicado** — `app/services/pregunta.py`: dos comentarios `# B5` seguidos dicen lo mismo.

## L. Abierto

- **L1 Un documento ya ingerido no recibe metadatos después**: hay que ingerir siempre con `--catalogo`. La ingesta
  de producción del 2026-11-16 se lanzó con él.
- **L2 El trigger no cubre mover un documento de colección.** Ningún código lo hace.
- **L3 El índice HNSW ya no lo usa ninguna consulta** y cuesta en la ingesta. Quitarlo después del despliegue.
- **L4 Un modelo de Ollama llamado `bge-m3:latest`** no queda con el identificador común.
- **L5 El texto de licencia que ve el público** dice, por ejemplo, «Sin declaración de licencia en todo el
  documento». Quizá un texto más neutro.
- **L6 El `downgrade` de `c7a2d4e8f613`** marca como Ollama también lo embebido con Cloudflare (lo reconoce su ADR).

## Segunda pasada, sobre las correcciones K (2026-11-22)

Auditó otra sesión, solo lectura: nada bloquea. Se corrigió en el mismo commit:

- [x] **K7 Un número de miles de dígitos daba 500** — `int()` de Python revienta pasados 4300 dígitos. Un número de
  referencia lleva hasta `MAX_DIGITOS_REFERENCIA` (9); test `test_k1_un_numero_de_miles_de_digitos_no_es_referencia`,
  visto en rojo con el `ValueError`. De paso, el comentario de `OPERADOR_DISTANCIA_COSENO` ya no dice que acelera el
  HNSW.

Queda abierto:

- **L7 Un rango que empieza en 1 respalda todo**: `[1-2020]` marca como citados los 5 fragmentos (el tope cuenta desde
  el inicio). No inventa citas fuera de lo entregado.
- **L8 Caracteres invisibles que no son de control** (espacio de ancho cero, BOM, `ㅤ`) pasan como título: la cita
  sale sin texto visible. Cerrarlo rechazando la categoría Unicode Cf o tratando como blanco lo que no tiene ningún
  carácter visible.
- **L9 Veredictos rebuscados en la tabla de licencias**: `publicar (no: derechos reservados)` publica (el paréntesis
  final se toma como firma), y una cabecera con dos columnas «Veredicto» se queda con la última. La tabla real da
  79 y 10, y ninguna fila con «reservad» queda para publicar.
- **L10 Un documento que la tabla no nombra queda como estaba**: si ya estaba verificado, sigue público y el comando
  sale con 0, con un aviso. Es el diseño anterior a K3.
- **L11 Errores de lectura del comando de licencias** salen con 1, pero con traceback y no con un mensaje.
- **L12 La medición pública de K2** corre sin espacio ni colección; la ruta pública real siempre lleva colección, así
  que la cifra (254 → 142 ms) cubre un alcance más amplio que el real.
