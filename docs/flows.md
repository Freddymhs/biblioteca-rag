# Flow Validation Document — biblioteca-rag

> Mantenido a mano. Describe qué ve quien usa el servicio.
> Última actualización: 2026-11-16 (FASE_3: paquetes de dominio y enrutamiento cálculo/significado).
>
> **Los cuerpos son literales**: salieron de la API real (`TestClient` contra Postgres + pgvector en
> contenedor, proveedores reemplazados por dobles). Los valores de `respuesta`, `distancia` y
> `creado_en` cambian con proveedores reales; la **forma** no. El contrato es el OpenAPI de `/docs`:
> si una forma cambia, se cambia aquí en el mismo commit.

## Convenciones

Por flujo: **Precondiciones** · **Pasos** · **Resultado esperado** · **Casos borde**.
Formato de error, en todos los endpoints: `{"error": "<mensaje>"}` (FastAPI nativo, sin envoltorio).

| Código | Cuándo |
|---|---|
| 404 | espacio o colección inexistente |
| 409 | slug repetido · mismo contenido ya ingerido en la colección · la colección está embebida con otro modelo (re-embeber) |
| 400 | `Content-Length` que no es un número |
| 413 | cuerpo HTTP de más de 101 MB (se rechaza por `Content-Length`, sin leerlo) · archivo de más de 100 MB |
| 422 | cuerpo inválido · archivo vacío, tipo no soportado, PDF dañado o sin texto · nombre de archivo de más de 500 caracteres o con caracteres de control |
| 502 | el proveedor de embeddings o el LLM falló, respondió en un formato inesperado o con texto vacío |
| 503 | proveedor o conector sin configurar en `.env` · la cola (Redis) no responde |

---

## Primer uso

### Levantar el servicio y crear la primera colección

**Precondiciones**: `.env` con proveedores (ver README) · `docker compose up --build -d` ·
`docker compose exec api alembic upgrade head`.

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
    "creado_en": "2026-11-16T09:49:03.669873Z"
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
      "pagina_inicio": 1,
      "pagina_fin": 1,
      "origen": "texto",
      "fragmento": "Riego del olivo El Kc del olivo es 0.65.",
      "distancia": 0.18333350519338076
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
      "pagina_inicio": null,
      "pagina_fin": null,
      "origen": "datos",
      "fragmento": "Factura N° 4521 del 2026-03-12, emitida por Agricola Los Olivos SpA, total 119.000 CLP.",
      "distancia": 0.0
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

### Buscar sin login y recibir fragmentos con cita
(por llenar)

### Superar el límite de uso
(por llenar)

### Intentar subir sin API key
(por llenar)

### Consultar desde un agente por MCP
(por llenar)
