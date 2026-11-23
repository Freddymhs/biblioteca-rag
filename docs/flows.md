# Flow Validation Document — biblioteca-rag

> Mantenido a mano. Describe qué ve quien usa el servicio.
> Última actualización: 2026-11-16 (FASE_6: decisiones de Freddy; contrato del portal).
>
> **Los cuerpos son literales**: salieron de la API real (`TestClient` contra Postgres + pgvector en
> contenedor, proveedores reemplazados por dobles). Los valores de `respuesta`, `distancia` y
> `creado_en` cambian con proveedores reales; la **forma** no. El contrato es el OpenAPI de `/docs`:
> si una forma cambia, se cambia aquí en el mismo commit.

## Convenciones

Por flujo: **Precondiciones** · **Pasos** · **Resultado esperado** · **Casos borde**.
Formato de error, en todos los endpoints: `{"error": "<mensaje>"}` (FastAPI nativo, sin envoltorio).

**Autenticación (FASE_4)**: todo `/api` **excepto `/api/publico`** exige el encabezado `X-API-Key` con la clave de
`API_KEY` (.env), también para leer: ahí están las colecciones personales. Los ejemplos de abajo la omiten por
brevedad. `/api/publico/*` y el MCP (`/mcp`) no piden clave, leen solo lo público y tienen límite de uso.

| Código | Cuándo |
|---|---|
| 404 | espacio o colección inexistente |
| 409 | slug repetido · mismo contenido ya ingerido en la colección · la colección está embebida con otro modelo (re-embeber) |
| 400 | `Content-Length` que no es un número |
| 401 | falta `X-API-Key` o no es la de `API_KEY` (se responde antes de leer el cuerpo) |
| 413 | cuerpo HTTP de más de 101 MB (se rechaza por `Content-Length`, sin leerlo) · archivo de más de 100 MB · en `POST …/documentos`, archivo de más de 10 MB o PDF de más de 30 páginas (va por `…/lotes`) · en `/api/publico` y `/mcp`, cuerpo de más de 16 KB (también sin `Content-Length`: se cuenta al recibir) |
| 422 | cuerpo inválido · archivo vacío, tipo no soportado, PDF dañado o sin texto · nombre de archivo de más de 500 caracteres o con caracteres de control |
| 429 | límite de uso de lo público superado: por IP por minuto, cuota diaria por IP o tope diario global (búsquedas y respuestas) |
| 502 | el proveedor de embeddings o el LLM falló, respondió en un formato inesperado o con texto vacío (en lo público, con un mensaje genérico) |
| 503 | proveedor o conector sin configurar en `.env` · la cola (Redis) no responde · `API_KEY` sin configurar (lo privado queda cerrado) · lo público sin Redis para aplicar el límite · lo público sin cupo para otra respuesta con LLM · lo público mientras la biblioteca está embebida con otro modelo |

---

## Primer uso

### Levantar el servicio y crear la primera colección

**Precondiciones**: `.env` con proveedores, `API_KEY` y `REDIS_PASSWORD` (ver README) ·
`docker compose up --build -d` (la API migra la base al arrancar).

**Pasos y resultado**:

#### POST /api/espacios → 201
```json
{
  "id": 1,
  "slug": "laboral",
  "nombre": "Laboral",
  "creado_en": "2026-11-16T09:49:03.669873Z"
}
```

#### POST /api/espacios/laboral/colecciones → 201
```json
{
  "id": 1,
  "espacio": "laboral",
  "slug": "agricultura",
  "nombre": "Agricultura",
  "paquete": null,
  "publica": false,
  "creado_en": "2026-11-16T09:49:03.669873Z"
}
```

#### GET /api/espacios → 200
```json
[
  {
    "id": 1,
    "slug": "laboral",
    "nombre": "Laboral",
    "creado_en": "2026-11-16T09:49:03.669873Z"
  }
]
```

#### GET /api/espacios/laboral/colecciones → 200
```json
[
  {
    "id": 1,
    "espacio": "laboral",
    "slug": "agricultura",
    "nombre": "Agricultura",
    "paquete": null,
    "publica": false,
    "creado_en": "2026-11-16T09:49:03.669873Z"
  }
]
```

**Casos borde**:

#### POST /api/espacios (repetido) → 409
```json
{
  "error": "Ya existe el espacio «laboral»"
}
```

#### POST /api/espacios (slug inválido) → 422
```json
{
  "error": "body → slug: String should match pattern '^[a-z0-9]+(-[a-z0-9]+)*$'"
}
```

## Ingesta

### Subir un PDF a una colección

`POST /api/espacios/{espacio}/colecciones/{coleccion}/documentos`, multipart, campo `archivo`.

#### POST …/documentos (PDF) → 201
```json
{
  "id": 1,
  "nombre_archivo": "olivo.pdf",
  "tipo": "pdf",
  "paginas": 3,
  "trozos": 2,
  "creado_en": "2026-11-16T09:49:03.669873Z",
  "licencia": null,
  "licencia_verificada": false,
  "titulo": null,
  "fuente": null,
  "anno": null,
  "paginas_sin_texto": [
    2,
    3
  ],
  "paginas_por_vision": [
    2
  ],
  "paginas_en_blanco": [
    3
  ],
  "extraccion_id": null,
  "paginas_sin_indexar": []
}
```

`paginas_sin_texto`: las páginas sin capa de texto (una figura sola cuenta como sin texto). De ellas,
`paginas_por_vision` las describió el modelo de visión (quedan buscables, con `origen: "vision"`),
`paginas_en_blanco` no se mandan al modelo (con una página en blanco inventa contenido) y
`paginas_sin_indexar` no se pudieron describir (visión desactivada o sin respuesta: van al log).
El nombre del archivo puede no tener extensión: el tipo se detecta por contenido.

#### GET …/documentos → 200
```json
[
  {
    "id": 1,
    "nombre_archivo": "olivo.pdf",
    "tipo": "pdf",
    "paginas": 3,
    "trozos": 2,
    "creado_en": "2026-11-16T09:49:03.669873Z",
    "licencia": null,
    "licencia_verificada": false,
    "titulo": null,
    "fuente": null,
    "anno": null
  }
]
```

### Cargar una carpeta entera

```bash
uv run python -m app.cli.ingestar <carpeta> --espacio laboral --coleccion agricultura \
  --excluir catalogo.json --excluir prompt.txt --excluir LIBROS_POR_REBUSCAR.md
```

Una línea por archivo (`[n/N] nombre: K trozos` o el motivo del rechazo) y al final el resumen, medido
el 2026-11-16 sobre 6 documentos del corpus:

```
Archivos: 6 · ingeridos: 6 · duplicados: 0 · rechazados: 0 · errores: 0 · trozos: 107
```

Sale con código 1 solo si hubo **errores** (proveedor caído, fallo inesperado); duplicados y rechazados
son esperables y no cambian el código de salida.

### Subir un archivo que no es un documento (vacío, tipo falso)

#### POST …/documentos (vacío) → 422
```json
{
  "error": "El archivo está vacío"
}
```

#### POST …/documentos (tipo falso) → 422
```json
{
  "error": "Tipo de archivo no soportado: se aceptan PDF y texto plano UTF-8"
}
```

#### POST …/documentos (sin texto) → 422
```json
{
  "error": "El archivo no tiene texto extraíble ni páginas que el modelo de visión pudiera describir (¿escaneado en blanco, o visión desactivada?)"
}
```

#### POST …/documentos (nombre demasiado largo) → 422
```json
{
  "error": "El nombre del archivo supera los 500 caracteres"
}
```

#### POST …/documentos (cuerpo de más de 101 MB) → 413
```json
{
  "error": "El cuerpo supera el máximo de 105906176 bytes"
}
```

### Subir dos veces el mismo archivo

Mismo contenido con otro nombre: no se extrae ni se embebe de nuevo, y no se duplican trozos.

#### POST …/documentos (mismo archivo) → 409
```json
{
  "error": "Ese contenido ya está en la colección «agricultura» como «olivo.pdf»"
}
```

## Preguntas

`POST /api/preguntas` con `{"pregunta", "espacio", "coleccion"?}`.

### Preguntar y recibir respuesta con cita

#### POST /api/preguntas (con respuesta) → 200
```json
{
  "respuesta": "El Kc del olivo es 0.65 [1].",
  "sabe": true,
  "citas": [
    {
      "documento_id": 1,
      "documento": "olivo.pdf",
      "titulo": "olivo.pdf",
      "pagina_inicio": 1,
      "pagina_fin": 1,
      "origen": "texto",
      "fragmento": "Riego del olivo El Kc del olivo es 0.65.",
      "distancia": 0.18333350519338076,
      "licencia": null,
      "fuente": null,
      "anno": null
    }
  ],
  "ruta": "semantica",
  "herramienta": null
}
```

`citas` trae los fragmentos que el LLM citó con `[n]` (todos los recuperados si no citó ninguno).
`origen`: `texto` (copiado del documento), `vision` (descripción generada por un modelo: el
prompt se lo dice al LLM) o `datos` (datos estructurados que confirmó una persona, FASE_3; un cliente
con un enum estricto `texto | vision` debe agregarlo). `pagina_inicio`/`pagina_fin`: rango del fragmento (iguales si cabe en una página; una tabla partida
entre dos páginas da un rango). Ambos `null` en texto plano. `distancia`: coseno, 0 = idéntico.

### Preguntar algo que no está en los datos («no lo sé»)

Si ningún trozo queda bajo `PREGUNTA_DISTANCIA_MAXIMA` (0,55), responde sin llamar al LLM. Si el LLM
contesta que el contexto no alcanza, la respuesta es la misma.

#### POST /api/preguntas (sin respuesta) → 200
```json
{
  "respuesta": "No lo sé: la respuesta no está en los documentos de esta biblioteca.",
  "sabe": false,
  "citas": [],
  "ruta": "semantica",
  "herramienta": null
}
```

### Preguntar dentro de un espacio vs una colección

Sin `coleccion`, busca en todas las colecciones del espacio. Nunca cruza espacios. Nunca compara
vectores de otro modelo de embeddings (`trozo.embedding_model`).

#### POST /api/preguntas (espacio inexistente) → 404
```json
{
  "error": "El espacio «nada» no existe"
}
```

## Ingesta en segundo plano (FASE_2)

### Subir una carpeta sin bloquear la API

`POST /api/espacios/{espacio}/colecciones/{coleccion}/lotes`, multipart, campo `archivos` repetido
(hasta 1 GB por petición y 100 MB por archivo, contados al copiar aunque no venga `Content-Length`).
Responde en cuanto los archivos quedan en disco y en la cola; el worker
(`arq app.worker.WorkerSettings`) los procesa de a uno. Sin Redis: 503 y no queda trabajo ni copia.

#### POST …/lotes → 202
```json
{
  "id": 1,
  "espacio": "laboral",
  "coleccion": "agricultura",
  "tipo": "lote",
  "estado": "pendiente",
  "total": 2,
  "procesados": 0,
  "ingeridos": 0,
  "duplicados": 0,
  "sin_cambios": 0,
  "rechazados": 0,
  "errores": 0,
  "eliminados": 0,
  "trozos": 0,
  "ultimo_error": null,
  "creado_en": "2026-11-16T09:49:03.669873Z",
  "actualizado_en": "2026-11-16T09:49:03.669873Z"
}
```

#### POST …/lotes (cola caída) → 503
```json
{
  "error": "La cola de trabajos (Redis) no responde"
}
```

Sin Redis no se crea el trabajo ni se copia nada (se verifica la cola antes).

### Consultar el avance

El estado se deriva de los contadores: `pendiente` → `en_curso` → `terminado` (procesados = total).
`duplicados`: mismo contenido que otro documento · `sin_cambios`: registro de un conector que no
cambió. Si el worker muere a mitad, un barrido (cada 10 min y al arrancar) cierra el trabajo con lo
que faltaba como error y el motivo en `ultimo_error`.

#### GET /api/trabajos/{id} → 200
```json
{
  "id": 1,
  "espacio": "laboral",
  "coleccion": "agricultura",
  "tipo": "lote",
  "estado": "pendiente",
  "total": 2,
  "procesados": 0,
  "ingeridos": 0,
  "duplicados": 0,
  "sin_cambios": 0,
  "rechazados": 0,
  "errores": 0,
  "eliminados": 0,
  "trozos": 0,
  "ultimo_error": null,
  "creado_en": "2026-11-16T09:49:03.669873Z",
  "actualizado_en": "2026-11-16T09:49:03.669873Z"
}
```

Medido el 2026-11-16 en Docker: lote de 2 PDF del corpus → `terminado 2/2`, 32 trozos, y la pregunta
sobre esos documentos respondida con cita.

### Sincronizar una colección con un conector

`POST …/sincronizaciones` con `{"conector": "resume"}`. El worker trae los registros y refleja altas,
cambios (el documento se reemplaza en un solo commit) y bajas (`eliminados`). Una fuente caída
termina el trabajo con `errores: 1` y el motivo en `ultimo_error`, sin borrar nada. Una fuente que
responde sin registros también es error si la colección tiene documentos: vaciarla exige
`"permitir_vaciar": true` (CLI: `--permitir-vaciar`). Por CLI:
`python -m app.cli.sincronizar --espacio personal --coleccion sobre-mi --conector resume`.

#### POST …/sincronizaciones → 202
```json
{
  "id": 2,
  "espacio": "laboral",
  "coleccion": "agricultura",
  "tipo": "sincronizacion",
  "estado": "pendiente",
  "total": null,
  "procesados": 0,
  "ingeridos": 0,
  "duplicados": 0,
  "sin_cambios": 0,
  "rechazados": 0,
  "errores": 0,
  "eliminados": 0,
  "trozos": 0,
  "ultimo_error": null,
  "creado_en": "2026-11-16T09:49:03.669873Z",
  "actualizado_en": "2026-11-16T09:49:03.669873Z"
}
```

#### POST …/sincronizaciones (conector desconocido) → 422
```json
{
  "error": "Conector desconocido «otro». Disponibles: ['resume']"
}
```

### Re-embeber al cambiar de modelo o de troceo

`python -m app.cli.reembeber --espacio laboral [--coleccion agricultura] [--retrocear]`. Un documento
por transacción; mientras corre, cada búsqueda ve solo los documentos del modelo activo. Si se
pregunta con un modelo que no tiene trozos en la colección, la API responde 409 con el comando a
correr, en vez de un «no lo sé» falso.

Cambiar `EMBEDDINGS_PROVIDER` entre `ollama` y `cloudflare` con bge-m3 **no** es cambiar de modelo:
los dos guardan el identificador común `bge-m3` (coseno 0,99999, medido en la FASE_6) y no hace falta
re-embeber. Ver `docs/decisions/DECISION_BGE_M3_IDENTIFICADOR_COMUN.md`.

Las colecciones con paquete (FASE_3) **no se re-trocean**: lo buscable es solo el trozo `datos` de lo
confirmado, y re-trocear embebería el texto crudo, también el de extracciones pendientes. Con
`--retrocear` sobre todo el espacio se re-embeben sin re-trocear (aviso en el log); nombradas con
`--coleccion`, 422. Re-embeber sin `--retrocear` conserva el trozo `datos` con el modelo nuevo.

## Paquetes de dominio (FASE_3)

### Crear una colección con paquete

Una colección elige su paquete por data (`paquete`). Hoy existe `facturas`; un nombre desconocido es 422.

#### POST /api/espacios/laboral/colecciones (con paquete) → 201
```json
{
  "id": 2,
  "espacio": "laboral",
  "slug": "facturas",
  "nombre": "Facturas",
  "paquete": "facturas",
  "publica": false,
  "creado_en": "2026-11-16T09:49:03.669873Z"
}
```

### Subir un documento: extracción pendiente, nada se embebe

En una colección con paquete, `POST …/documentos` extrae el texto (Docling), le pide al LLM los datos
con el esquema del paquete y guarda una extracción **pendiente**: `trozos: 0`. Lotes, CLI y conectores
responden 422 para estas colecciones: todo pasa por la confirmación.

#### POST …/documentos (colección con paquete) → 201
```json
{
  "id": 2,
  "nombre_archivo": "factura.txt",
  "tipo": "txt",
  "paginas": null,
  "trozos": 0,
  "creado_en": "2026-11-16T09:49:03.669873Z",
  "licencia": null,
  "licencia_verificada": false,
  "titulo": null,
  "fuente": null,
  "anno": null,
  "paginas_sin_texto": [],
  "paginas_por_vision": [],
  "paginas_en_blanco": [],
  "extraccion_id": 1,
  "paginas_sin_indexar": []
}
```

### El formulario de confirmación

`json_schema` es el formulario; `propuesta` es lo que leyó el LLM (puede no validar: `errores` dice por
qué). Medido con llama3.2:3b: folio «Pc 4521», moneda «DOL», fecha del año 205 o 2003. Por eso se confirma.

#### GET /api/extracciones/{id}/formulario → 200
```json
{
  "extraccion_id": 1,
  "documento_id": 2,
  "documento": "factura.txt",
  "paquete": "facturas",
  "estado": "pendiente",
  "json_schema": {
    "$defs": {
      "LineaFactura": {
        "properties": {
          "descripcion": {
            "maxLength": 200,
            "title": "Descripcion",
            "type": "string"
          },
          "cantidad": {
            "anyOf": [
              {
                "exclusiveMinimum": 0.0,
                "type": "number"
              },
              {
                "type": "string"
              }
            ],
            "title": "Cantidad"
          },
          "precio_unitario": {
            "anyOf": [
              {
                "minimum": 0.0,
                "type": "number"
              },
              {
                "type": "string"
              }
            ],
            "title": "Precio Unitario"
          }
        },
        "required": [
          "descripcion",
          "cantidad",
          "precio_unitario"
        ],
        "title": "LineaFactura",
        "type": "object"
      }
    },
    "description": "Datos de una factura. Su JSON Schema es el formulario de confirmación.",
    "properties": {
      "numero": {
        "description": "folio",
        "maxLength": 200,
        "minLength": 1,
        "title": "Numero",
        "type": "string"
      },
      "fecha": {
        "description": "fecha de emisión",
        "format": "date",
        "title": "Fecha",
        "type": "string"
      },
      "emisor": {
        "maxLength": 200,
        "minLength": 1,
        "title": "Emisor",
        "type": "string"
      },
      "rut_emisor": {
        "anyOf": [
          {
            "maxLength": 200,
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Rut Emisor"
      },
      "receptor": {
        "anyOf": [
          {
            "maxLength": 200,
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Receptor"
      },
      "moneda": {
        "description": "código ISO 4217, ej. CLP o USD",
        "pattern": "^[A-Z]{3}$",
        "title": "Moneda",
        "type": "string"
      },
      "neto": {
        "anyOf": [
          {
            "minimum": 0.0,
            "type": "number"
          },
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Neto"
      },
      "iva": {
        "anyOf": [
          {
            "minimum": 0.0,
            "type": "number"
          },
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Iva"
      },
      "total": {
        "anyOf": [
          {
            "minimum": 0.0,
            "type": "number"
          },
          {
            "type": "string"
          }
        ],
        "title": "Total"
      },
      "lineas": {
        "items": {
          "$ref": "#/$defs/LineaFactura"
        },
        "title": "Lineas",
        "type": "array"
      }
    },
    "required": [
      "numero",
      "fecha",
      "emisor",
      "moneda",
      "total"
    ],
    "title": "Factura",
    "type": "object"
  },
  "propuesta": {
    "iva": "19000",
    "neto": "100000",
    "fecha": "2026-03-12",
    "total": "119000",
    "emisor": "Agricola Los Olivos SpA",
    "lineas": [],
    "moneda": "CLP",
    "numero": "4521",
    "receptor": null,
    "rut_emisor": null
  },
  "errores": [],
  "confirmados": null
}
```

### Confirmar los datos

Se valida contra el esquema del paquete (una fecha fuera de 1990–2100, un monto negativo o de más de
15 dígitos o 2 decimales, o sin `moneda`, es 422: la moneda no se supone). Lo confirmado se embebe como
un trozo con `origen: "datos"`, y recién ahí lo ven la búsqueda y el SQL. Dos confirmaciones
simultáneas: la segunda relee la fila con bloqueo, ve que ya está confirmada y responde 409.

#### POST /api/extracciones/{id}/confirmacion (inválida) → 422
```json
{
  "error": "Datos inválidos para «facturas»: 1 validation error for Factura\nfecha\n  Value error, año 1203 fuera de 1990–2100 [type=value_error, input_value='1203-03-26', input_type=str]\n    For further information visit https://errors.pydantic.dev/2.14/v/value_error"
}
```

#### POST /api/extracciones/{id}/confirmacion → 200
```json
{
  "extraccion_id": 1,
  "estado": "confirmada",
  "trozos": 1
}
```

#### POST /api/extracciones/{id}/confirmacion (ya confirmada) → 409
```json
{
  "error": "La extracción 2 ya está confirmada: corregirla con PUT"
}
```

### Rechazar una propuesta pendiente

`POST /api/extracciones/{id}/rechazo`, sin cuerpo. Borra el documento y su extracción (nunca tuvo
trozos), así el mismo archivo puede volver a subirse. Una confirmada no se rechaza: se corrige (409).

#### POST /api/extracciones/{id}/rechazo → 200
```json
{
  "extraccion_id": 1,
  "documento_id": 1,
  "documento_eliminado": true
}
```

#### POST /api/extracciones/{id}/rechazo (confirmada) → 409
```json
{
  "error": "La extracción 2 no está pendiente: corregirla con PUT"
}
```

### Corregir una extracción confirmada

`PUT /api/extracciones/{id}/confirmacion` con el objeto completo (mismo cuerpo que el `POST`). Valida
igual y reemplaza `confirmados` y el trozo `datos` en una sola transacción: cálculos y búsqueda ven la
versión corregida o la anterior, nunca una mezcla. A una pendiente, 409 (se confirma con `POST`).

#### PUT /api/extracciones/{id}/confirmacion → 200
```json
{
  "extraccion_id": 2,
  "estado": "confirmada",
  "trozos": 1
}
```

#### PUT /api/extracciones/{id}/confirmacion (pendiente) → 409
```json
{
  "error": "La extracción 2 no está confirmada: confirmarla con POST"
}
```

### Preguntar un cálculo: herramienta SQL fija

En una colección con paquete, un clasificador (LangGraph + LLM) decide «cálculo» o «significado». Un
cálculo elige una herramienta del paquete (enum cerrado) y argumentos que valida Pydantic; el SQL es
fijo y parametrizado, y la respuesta la escribe un formateador, no el LLM (`ruta: "sql"`). Cualquier
decisión inválida va a la búsqueda semántica (`ruta: "semantica"`). Herramientas de `facturas`:
`total_facturado`, `cantidad_de_facturas`, `facturado_por_emisor`, `factura_mas_alta`. Totales,
ranking y máximo van **por moneda** (5.000 CLP no queda sobre 1.000 USD). Cada SQL filtra por colección,
paquete y estado confirmado, todos como parámetros.

#### POST /api/preguntas (cálculo por SQL) → 200
```json
{
  "respuesta": "Total facturado: 119.000 CLP en 1 factura.",
  "sabe": true,
  "citas": [
    {
      "documento_id": 2,
      "documento": "factura.txt",
      "titulo": "factura.txt",
      "pagina_inicio": null,
      "pagina_fin": null,
      "origen": "datos",
      "fragmento": "Factura N° 4521 del 2026-03-12, emitida por Agricola Los Olivos SpA, total 119.000 CLP.",
      "distancia": 0.0,
      "licencia": null,
      "fuente": null,
      "anno": null
    }
  ],
  "ruta": "sql",
  "herramienta": "total_facturado"
}
```

#### POST /api/preguntas (cálculo sin datos confirmados) → 200

Sin filas no hay dato: `sabe: false` y sin citas, igual que un «no lo sé».

```json
{
  "respuesta": "No hay facturas confirmadas.",
  "sabe": false,
  "citas": [],
  "ruta": "sql",
  "herramienta": "cantidad_de_facturas"
}
```

## Servicio público (FASE_4)

Lo público lee con el rol de Postgres `biblioteca_publico` (RLS): solo **colecciones públicas** y, dentro de ellas,
solo **documentos con licencia verificada**. Una colección privada no existe para este rol (404, igual que una
inexistente). Nunca se entrega el documento completo: solo fragmentos con cita.

### Publicar una colección y verificar una licencia (con API key)

La colección se marca pública; cada documento necesita además su licencia verificada por una persona (tarea 4.6:
`docs/backlog/LICENCIAS_AGRICULTURA_2026-11-16.md`). Sin eso, la colección pública no muestra nada.

#### PATCH /api/espacios/laboral/colecciones/agricultura → 200
```json
{
  "id": 1,
  "espacio": "laboral",
  "slug": "agricultura",
  "nombre": "Agricultura",
  "paquete": null,
  "publica": true,
  "creado_en": "2026-11-16T11:32:52.824382Z"
}
```

Cuerpo: `{"publica": true}`.

Una colección con paquete (facturas) no se publica: lo impiden la API y la base.

#### PATCH …/colecciones/facturas (con paquete) → 422
```json
{
  "error": "La colección «facturas» usa el paquete «facturas»: sus datos no se publican"
}
```

#### PUT /api/espacios/laboral/colecciones/agricultura/documentos/{id}/licencia → 200
```json
{
  "id": 1,
  "nombre_archivo": "olivo.pdf",
  "tipo": "pdf",
  "paginas": 2,
  "trozos": 2,
  "creado_en": "2026-11-16T11:32:52.824382Z",
  "licencia": "CC BY 4.0",
  "licencia_verificada": true,
  "titulo": null,
  "fuente": null,
  "anno": null
}
```

Cuerpo: `{"licencia": "CC BY 4.0", "verificada": true}`.

#### PUT …/documentos/{id}/licencia (verificada sin nombre) → 422
```json
{
  "error": "Una licencia verificada necesita el nombre de la licencia"
}
```

### Ver qué hay público

#### GET /api/publico/colecciones → 200
```json
[
  {
    "espacio": "laboral",
    "slug": "agricultura",
    "nombre": "Agricultura",
    "documentos": 1
  }
]
```

`documentos` cuenta solo los que tienen licencia verificada.

### Buscar sin login y recibir fragmentos con cita

Sin LLM: los fragmentos bajo la distancia máxima, con documento, páginas y licencia (a citar si se reproducen).
Parámetros: `q` (obligatorio), `espacio` y `coleccion` (opcionales; una colección exige su espacio).

#### GET /api/publico/buscar?q=Kc del olivo → 200
```json
{
  "fragmentos": [
    {
      "documento_id": 1,
      "documento": "olivo.pdf",
      "titulo": "olivo.pdf",
      "pagina_inicio": 1,
      "pagina_fin": 1,
      "origen": "texto",
      "fragmento": "Riego del olivo El Kc del olivo es 0.65.",
      "distancia": 0.18333350519338076,
      "licencia": "CC BY 4.0",
      "fuente": null,
      "anno": null
    },
    {
      "documento_id": 1,
      "documento": "olivo.pdf",
      "titulo": "olivo.pdf",
      "pagina_inicio": 2,
      "pagina_fin": 2,
      "origen": "texto",
      "fragmento": "Poda del olivo",
      "distancia": 0.4993757903947946,
      "licencia": "CC BY 4.0",
      "fuente": null,
      "anno": null
    }
  ]
}
```

#### GET /api/publico/buscar?q=potasio&espacio=personal&coleccion=sobre-mi → 404
```json
{
  "error": "El espacio «personal» no existe"
}
```

### Pedir una respuesta redactada

`POST /api/publico/preguntas` con `{"pregunta": "...", "espacio": null, "coleccion": null}`. Usa el LLM: tiene un
límite por IP más bajo y un tope diario global.

#### POST /api/publico/preguntas → 200
```json
{
  "respuesta": "El Kc del olivo es 0.65 [1].",
  "sabe": true,
  "citas": [
    {
      "documento_id": 1,
      "documento": "olivo.pdf",
      "titulo": "olivo.pdf",
      "pagina_inicio": 1,
      "pagina_fin": 1,
      "origen": "texto",
      "fragmento": "Riego del olivo El Kc del olivo es 0.65.",
      "distancia": 0.18333350519338076,
      "licencia": "CC BY 4.0",
      "fuente": null,
      "anno": null
    }
  ],
  "ruta": "semantica",
  "herramienta": null
}
```

### Superar el límite de uso

- **Por minuto y por IP**, para toda petición (cuenta antes de validar, es barato): `LIMITE_BUSQUEDAS_POR_MINUTO`
  (colecciones y búsqueda) y `LIMITE_RESPUESTAS_POR_MINUTO` (respuesta redactada).
- **Cuotas diarias**, solo cuando la petición ya es válida (un 404 o un 422 no las gasta): por IP
  (`LIMITE_BUSQUEDAS_DIARIAS_POR_IP`, `LIMITE_RESPUESTAS_DIARIAS_POR_IP`) y globales (`LIMITE_BUSQUEDAS_DIARIAS`,
  `LIMITE_RESPUESTAS_DIARIAS`). Primero la de la IP: una IP pasada de la suya no gasta la de todos.
- Una IPv6 cuenta por su red /64. Ventanas fijas desde el primer uso. Detrás de Cloudflare la IP sale de
  `CF-Connecting-IP` solo si `CONFIAR_EN_CF_CONNECTING_IP=true`; si no, ese encabezado se ignora.

#### GET /api/publico/colecciones (límite superado) → 429
```json
{
  "error": "Límite de 1 usos superado; vuelve a intentar en 60 s"
}
```

Sin Redis no hay límite que aplicar, y lo público no se sirve (el detalle va al log, no a la respuesta):

#### GET /api/publico/colecciones (Redis caído) → 503
```json
{
  "error": "El servicio público no está disponible ahora: vuelve a intentar en unos minutos"
}
```

#### POST /api/publico/preguntas (cuota diaria de la IP) → 429
```json
{
  "error": "Límite de 1 usos superado; vuelve a intentar en 86400 s"
}
```

A lo más `MAX_RESPUESTAS_PUBLICAS_SIMULTANEAS` respuestas con LLM a la vez; las demás no esperan (un hilo esperando
120 s al LLM le quitaría hilos a lo privado y a `/health`) y no gastan cuota:

#### POST /api/publico/preguntas (sin cupo) → 503
```json
{
  "error": "Hay demasiadas respuestas en curso: vuelve a intentar en unos segundos"
}
```

Lo público tiene un tope de cuerpo de 16 KB (una pregunta cabe en 2.000 caracteres):

#### POST /api/publico/preguntas (cuerpo de 20 KB) → 413
```json
{
  "error": "El cuerpo supera el máximo de 16384 bytes"
}
```

Los errores de los proveedores y de mantenimiento no le cuentan a un anónimo qué hay detrás (el detalle va al log;
quien tiene la clave lo ve en `/api/preguntas`):

#### POST /api/publico/preguntas (LLM caído) → 502
```json
{
  "error": "Un servicio externo no respondió: vuelve a intentar en unos minutos"
}
```

#### GET /api/publico/buscar (embebida con otro modelo) → 503
```json
{
  "error": "La biblioteca se está actualizando: vuelve a intentar más tarde"
}
```

### Intentar escribir (o leer lo privado) sin API key

#### POST /api/espacios (sin X-API-Key) → 401
```json
{
  "error": "Falta la API key o no es válida (encabezado X-API-Key)"
}
```

#### POST /api/espacios (sin API_KEY configurada en .env) → 503
```json
{
  "error": "La API no tiene API_KEY configurada: lo privado está cerrado"
}
```

### Subir algo pesado

`POST …/documentos` convierte dentro de la petición; lo pesado (más de 10 MB o de 30 páginas) va por la cola, donde
el worker convierte de a uno (D1).

#### POST …/documentos (PDF pesado) → 413
```json
{
  "error": "Archivo pesado (855 bytes, 2 páginas; el máximo aquí es 10485760 bytes y 1 páginas): súbelo por POST …/lotes, que lo convierte en segundo plano"
}
```

Un lote a una colección con paquete se rechaza antes de copiar nada (F4):

#### POST …/lotes (colección con paquete) → 422
```json
{
  "error": "La colección «facturas» usa el paquete «facturas»: sus documentos se suben de a uno por POST …/documentos y se confirman"
}
```

Un cálculo cita como mucho 20 documentos y lo dice en la respuesta: «Total facturado: … en 25 facturas. (Se citan 20
de 25 documentos.)» (F1).

### Consultar desde un agente por MCP

Streamable HTTP en `/mcp`, sin estado y en JSON. Tools: `buscar` y `preguntar`, de solo lectura
(`readOnlyHint: true`), con los mismos datos y el mismo límite por IP que `/api/publico`. Solo acepta los `Host` de
`MCP_HOSTS_PERMITIDOS` (protección del SDK contra DNS rebinding). Un error de dominio vuelve como `isError: true` con
su código: `"Error executing tool buscar: 404: El espacio «personal» no existe"`.

Encabezados: `Content-Type: application/json`, `Accept: application/json, text/event-stream`.

#### POST /mcp (tools/call buscar)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "buscar",
    "arguments": {
      "pregunta": "Kc del olivo"
    }
  }
}
```

#### → 200
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "text": "{\n  \"fragmentos\": [\n    {\n      \"documento_id\": 1,\n      \"documento\": \"olivo.txt\",\n      \"pagina_inicio\": null,\n      \"pagina_fin\": null,\n      \"origen\": \"texto\",\n      \"fragmento\": \"El Kc del olivo es 0.65 en riego.\",\n      \"distancia\": 0.18333350519338076,\n      \"licencia\": \"CC BY 4.0\"\n    }\n  ]\n}",
        "type": "text"
      }
    ],
    "isError": false,
    "structuredContent": {
      "fragmentos": [
        {
          "documento_id": 1,
          "documento": "olivo.txt",
          "titulo": "olivo.txt",
          "pagina_inicio": null,
          "pagina_fin": null,
          "origen": "texto",
          "fragmento": "El Kc del olivo es 0.65 en riego.",
          "distancia": 0.18333350519338076,
          "licencia": "CC BY 4.0",
          "fuente": null,
          "anno": null
        }
      ]
    }
  }
}
```

## Observabilidad (FASE_5)

### Ver qué hizo una respuesta: trozos, latencia por etapa y proveedor

Toda respuesta HTTP trae el encabezado `X-Traza-Id` (también las públicas y las del MCP). Con
`docker compose --profile trazas up -d` y `TRAZAS_OTLP_URL=http://jaeger:4318/v1/traces` en `.env` (fuera de Docker:
`http://127.0.0.1:4318/v1/traces`), la traza se abre en `http://127.0.0.1:16686/trace/<X-Traza-Id>` (Jaeger local,
sin cuenta ni llave; solo en esta máquina). En producción la interfaz se publica solo en `127.0.0.1` del anfitrión:
se mira con `ssh -L 16686:127.0.0.1:16686 <mac-mini>`. El worker no emite trazas.

Etapas (cada span dura lo que tardó): `preguntar` o `buscar_publico` → `embeber_pregunta` → `buscar_trozos` →
`redactar`; en una colección con paquete, `clasificar` y `calcular_sql`; al subir un PDF con páginas sin texto,
`describir_imagen`. El span HTTP se nombra con la plantilla de la ruta (`GET /api/espacios/{espacio}/colecciones`),
nunca con la URL cruda; una ruta que no es de la app queda como `GET (sin ruta)`. Lo que guarda cada traza:

| Atributo | Dónde | Qué |
|---|---|---|
| `biblioteca.alcance` | span HTTP | `publico`, `privado` u `otro` |
| `biblioteca.pregunta.largo` | `preguntar`, `buscar_publico` | caracteres de la pregunta: **nunca el texto** |
| `biblioteca.espacio`, `biblioteca.coleccion` | ídem | solo si existen en el catálogo (no texto libre de un visitante) |
| `biblioteca.proveedor.embeddings` / `.llm` | `embeber_pregunta` / `redactar` | ej. `ollama:bge-m3`, `ChatOllama:llama3.2:3b` |
| `biblioteca.trozos.candidatos`, `.distancias` | `buscar_trozos` | ids de trozo y su distancia coseno, en orden |
| `biblioteca.trozos.usados` | `preguntar`, `buscar_publico`, `calcular_sql` | ids de los trozos citados en la respuesta |
| `biblioteca.decision`, `biblioteca.herramienta` | `clasificar`, `calcular_sql` | `calculo`/`significado` y la herramienta SQL (solo si es una del paquete) |
| `error.type` | cualquier span | ante un error, **solo el tipo** (`DataError`, `RuntimeError`…): nunca el mensaje ni la pila |

**No se guarda** el texto de ninguna pregunta ni ninguna IP. El span HTTP se nombra con la ruta **sin query**
(`GET /api/publico/buscar`, nunca `?q=…`). Un error no deja su mensaje (con Postgres traería el SQL y el vector de
la pregunta) y los engines usan `hide_parameters`. Solo se exportan spans de la app: la instrumentación nativa de
FastAPI 0.163 (guarda `url.query`) está apagada, el middleware de OpenTelemetry del SDK de MCP (guarda el nombre de
tool que manda el cliente y acepta su `traceparent`) está quitado, y un filtro descarta cualquier otro span.
LangSmith, que viene con LangChain, está apagado por código y en compose.

Prueba real (Ollama, 2026-11-16), traza de un `POST /api/publico/preguntas`, como la muestra Jaeger:

```
POST /api/publico/preguntas   118506.7 ms  biblioteca.alcance=publico
preguntar                     118444.6 ms  pregunta.largo=74 · sabe=true · trozos.usados=[6]
embeber_pregunta                 178.1 ms  proveedor.embeddings=ollama:bge-m3
buscar_trozos                     13.6 ms  trozos.candidatos=[5,6,4,2,1] · distancias=[0.338,0.351,0.471,0.506,0.510]
redactar                      118251.3 ms  proveedor.llm=ChatOllama:llama3.2:3b
```

### Uso público por día (con API key)

`GET /api/uso?dias=N` (1 a 90; por defecto 7), de hoy hacia atrás, en UTC. REST y MCP cuentan juntos. Una búsqueda o
respuesta cuenta cuando ya se respondió: un 404, un 422 o un 502 del proveedor no cuentan. Un 429 cuenta en el uso
que lo recibió. Si Redis falla al contar, la respuesta sale igual (el conteo se pierde y queda en el log). Son solo conteos (sin IPs ni preguntas) y duran 90 días en Redis. Es privada: con el resto de `/api`,
exige la clave.

#### GET /api/uso?dias=2 → 200
```json
[
  {
    "fecha": "2026-11-16",
    "busquedas": 2,
    "respuestas": 1,
    "rechazos_429": {
      "busqueda": 0,
      "respuesta": 1
    }
  },
  {
    "fecha": "2026-11-15",
    "busquedas": 0,
    "respuestas": 0,
    "rechazos_429": {
      "busqueda": 0,
      "respuesta": 0
    }
  }
]
```

#### GET /api/uso (sin X-API-Key) → 401
```json
{
  "error": "Falta la API key o no es válida (encabezado X-API-Key)"
}
```

#### GET /api/uso?dias=91 → 422
```json
{
  "error": "query → dias: Input should be less than or equal to 90"
}
```

## Para quien escribe el cliente del portal (FASE_6)

Decisión: `docs/decisions/DECISION_PORTAL_CONSUME_PUBLICO.md`. El chat del portal de AgriPlan usa solo lo público,
**desde el navegador** y **sin clave**.

### Las dos llamadas

| Llamada | Para qué | LLM | Tarda |
|---|---|---|---|
| `GET /api/publico/buscar?q=<texto>[&espacio=<slug>&coleccion=<slug>]` | fragmentos con cita | no | décimas de segundo |
| `POST /api/publico/preguntas` con `{"pregunta": "…", "espacio": null, "coleccion": null}` | respuesta redactada con cita | sí | segundos (ver tarea 6.5) |

- `Content-Type: application/json` en el `POST`; nada de `X-API-Key`.
- `q` y `pregunta`: de 1 a 2.000 caracteres. El cuerpo entero, hasta 16 KB.
- `coleccion` exige `espacio`; sin los dos, se busca en todas las colecciones públicas.
- Toda respuesta trae `X-Traza-Id` (legible desde el navegador): sirve para reportar un caso raro.

#### GET /api/publico/buscar?q=tuna y cochinilla → 200
```json
{
  "fragmentos": [
    {
      "documento_id": 4,
      "documento": "tuna.pdf",
      "titulo": "Cultivo de la tuna y crianza de la cochinilla",
      "pagina_inicio": null,
      "pagina_fin": null,
      "origen": "texto",
      "fragmento": "Tuna y cochinilla en el valle.",
      "distancia": 0.0,
      "licencia": "Reproducción permitida citando la fuente (no CC)",
      "fuente": "INIA Perú",
      "anno": 2002
    }
  ]
}
```

#### POST /api/publico/preguntas → 200
```json
{
  "respuesta": "La cochinilla se cría sobre la tuna [1].",
  "sabe": true,
  "citas": [
    {
      "documento_id": 4,
      "documento": "tuna.pdf",
      "titulo": "Cultivo de la tuna y crianza de la cochinilla",
      "pagina_inicio": null,
      "pagina_fin": null,
      "origen": "texto",
      "fragmento": "Tuna y cochinilla en el valle.",
      "distancia": 0.2924519181251526,
      "licencia": "Reproducción permitida citando la fuente (no CC)",
      "fuente": "INIA Perú",
      "anno": 2002
    }
  ],
  "ruta": "semantica",
  "herramienta": null
}
```

### Qué mostrar de una cita

| Campo | Qué es |
|---|---|
| `titulo` | **lo que se muestra**: el título real del documento o, si no tiene, el nombre del archivo (nunca vacío) |
| `documento` | nombre del archivo (para un enlace interno o un registro, no para mostrar) |
| `pagina_inicio`, `pagina_fin` | rango de páginas (iguales si cabe en una; `null` en texto plano) |
| `fuente`, `anno` | institución y año de publicación, si se conocen (`null` si no) |
| `licencia` | la licencia del documento: varias exigen citar la fuente al reproducir el fragmento |
| `origen` | `texto` (copiado del documento), `vision` (descrito por un modelo de una imagen) o `datos` |
| `fragmento` | el texto que respalda la respuesta |
| `distancia` | 0 = idéntico; sirve para ordenar, no para mostrar |

En la respuesta redactada, cada `[n]` del texto es la cita n-ésima de `citas` (en orden).

### «No lo sé» es una respuesta

`sabe: false` y `citas: []`: el chat lo muestra tal cual. Pasa cuando ningún fragmento es relevante y cuando el
modelo respondió sin ninguna referencia `[n]` válida (6.2).

#### POST /api/publico/preguntas (el modelo no citó) → 200
```json
{
  "respuesta": "No lo sé: la respuesta no está en los documentos de esta biblioteca.",
  "sabe": false,
  "citas": [],
  "ruta": "semantica",
  "herramienta": null
}
```

### Errores que el cliente tiene que manejar

Todos con el cuerpo `{"error": "<mensaje>"}`. Los cuerpos literales de 404, 413, 429, 502 y 503 están en «Servicio
público (FASE_4)»; los de 422, aquí abajo.

| Código | Cuándo | Qué hacer |
|---|---|---|
| 404 | `espacio`/`coleccion` que no existe o no es pública | quitar el filtro |
| 413 | cuerpo de más de 16 KB | acortar |
| 422 | pregunta vacía o de más de 2.000 caracteres, `coleccion` sin `espacio` | validar antes de enviar |
| 429 | se pasó el límite por IP o un tope diario; el mensaje dice en cuántos segundos reintentar | esperar ese tiempo |
| 502 | el proveedor externo (embeddings o LLM) no respondió | reintentar en unos minutos |
| 503 | demasiadas respuestas con LLM a la vez, servicio sin Redis, o biblioteca re-embebiéndose | reintentar en segundos |

#### POST /api/publico/preguntas (pregunta vacía) → 422
```json
{
  "error": "body → pregunta: String should have at least 1 character"
}
```

#### POST /api/publico/preguntas (colección sin espacio) → 422
```json
{
  "error": "body: Value error, una colección se nombra junto a su espacio"
}
```

### Límites (por IP del visitante)

30 búsquedas y 5 respuestas por minuto; 500 búsquedas y 20 respuestas por día; en total, 10.000 búsquedas y 200
respuestas por día; 2 respuestas con LLM a la vez. Por eso se llama **desde el navegador**: desde el servidor del
portal, todos los visitantes compartirían una IP.

### CORS

El origen del portal se habilita por configuración: `CORS_ORIGINS=["https://<dominio del portal>"]` en el `.env` del
servidor (lista JSON; vacía = ningún origen cruzado). Preflight `OPTIONS` respondido por el motor; expone
`X-Traza-Id`. Sin credenciales (no hay cookies).

