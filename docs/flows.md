# Flow Validation Document — biblioteca-rag

> Mantenido a mano. Describe qué ve quien usa el servicio.
> Última actualización: 2026-11-16 (FASE_1, tras la auditoría A1–A13).
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
| 409 | slug repetido · mismo contenido ya ingerido en la colección |
| 400 | `Content-Length` que no es un número |
| 413 | cuerpo HTTP de más de 101 MB (se rechaza por `Content-Length`, sin leerlo) · archivo de más de 100 MB |
| 422 | cuerpo inválido · archivo vacío, tipo no soportado, PDF dañado o sin texto · nombre de archivo de más de 500 caracteres o con caracteres de control |
| 502 | el proveedor de embeddings o el LLM falló, respondió en un formato inesperado o con texto vacío |
| 503 | proveedor sin configurar en `.env` (faltan credenciales) |

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
  "creado_en": "2026-11-16T06:12:49.219619Z"
}
```

#### POST /api/espacios/laboral/colecciones → 201
```json
{
  "id": 1,
  "espacio": "laboral",
  "slug": "agricultura",
  "nombre": "Agricultura",
  "creado_en": "2026-11-16T06:12:49.219619Z"
}
```

#### GET /api/espacios → 200
```json
[
  {
    "id": 1,
    "slug": "laboral",
    "nombre": "Laboral",
    "creado_en": "2026-11-16T06:12:49.219619Z"
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
    "creado_en": "2026-11-16T06:12:49.219619Z"
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
  "creado_en": "2026-11-16T06:12:49.219619Z",
  "paginas_sin_texto": [
    2
  ]
}
```

`paginas_sin_texto` lista las páginas sin capa de texto: no se indexan hasta la FASE_2 (visión) y
quedan en el log. El nombre del archivo puede no tener extensión: el tipo se detecta por contenido.

#### GET …/documentos → 200
```json
[
  {
    "id": 1,
    "nombre_archivo": "olivo.pdf",
    "tipo": "pdf",
    "paginas": 3,
    "trozos": 2,
    "creado_en": "2026-11-16T06:12:49.219619Z"
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
  "error": "El archivo no tiene texto extraíble (¿escaneado?). Las páginas sin texto se indexarán con visión en la FASE_2."
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
      "fragmento": "Riego del olivo El Kc del olivo es 0.65.",
      "distancia": 0.18333350519338076
    }
  ]
}
```

`citas` trae los fragmentos que el LLM citó con `[n]` (todos los recuperados si no citó ninguno).
`pagina_inicio`/`pagina_fin`: rango del fragmento (iguales si cabe en una página; una tabla partida
entre dos páginas da un rango). Ambos `null` en texto plano. `distancia`: coseno, 0 = idéntico.

### Preguntar algo que no está en los datos («no lo sé»)

Si ningún trozo queda bajo `PREGUNTA_DISTANCIA_MAXIMA` (0,55), responde sin llamar al LLM. Si el LLM
contesta que el contexto no alcanza, la respuesta es la misma.

#### POST /api/preguntas (sin respuesta) → 200
```json
{
  "respuesta": "No lo sé: la respuesta no está en los documentos de esta biblioteca.",
  "sabe": false,
  "citas": []
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

## Servicio público (FASE_4)

### Buscar sin login y recibir fragmentos con cita
(por llenar)

### Superar el límite de uso
(por llenar)

### Intentar subir sin API key
(por llenar)

### Consultar desde un agente por MCP
(por llenar)
