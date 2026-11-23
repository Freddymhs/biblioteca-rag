# DECISION: bge-m3 de Ollama y de Cloudflare comparten identificador (auditoría B2, tarea 6.8)

**Fecha**: 2026-11-16 · **Estado**: aplicada (FASE_6, tarea 6.8)

## Contexto

Cada trozo guarda en `embedding_model` con qué modelo se embebió, y la búsqueda solo compara vectores del mismo
identificador. Hasta hoy era `proveedor:modelo`: `ollama:bge-m3` y `cloudflare:@cf/baai/bge-m3`. Pasar de un
proveedor al otro dejaba el corpus invisible hasta re-embeberlo entero (auditoría B2), aunque sea el mismo modelo.

## Medición (`scripts/benchmark.py`, ThinkPad, 2026-11-16)

| Chequeo | Resultado |
|---|---|
| coseno del mismo texto, Ollama vs Cloudflare (5 textos, español e inglés) | mínimo **0,999991** (umbral 0,99) |
| control: coseno entre textos distintos, un proveedor contra el otro (20 pares) | máximo 0,4634 |
| mayor diferencia en un componente del vector | 7,6 × 10⁻⁴ |
| embedding de una pregunta, Ollama (mediana de 10) | 0,20–0,25 s en tres corridas |
| embedding de una pregunta, Cloudflare (mediana de 10) | 0,16–0,73 s en tres corridas (red) |

El control prueba que el chequeo distingue: si las dos llamadas fueran al mismo proveedor por error, o el coseno
diera alto para cualquier par, los textos distintos también darían cerca de 1. Dan 0,46.

## Decisión

1. **Un identificador común, `bge-m3`**, para los dos: `MODELOS_EQUIVALENTES` en `app/config/constantes.py`. Un
   trozo embebido con uno se encuentra preguntando con el otro, sin re-embeber.
2. **Solo pares medidos.** Un modelo sin equivalencia medida sigue con `proveedor:modelo`. Sumar uno exige correr
   este benchmark y que pase el umbral.
3. **Las trazas siguen diciendo quién respondió** (`ProveedorDeEmbeddings.quien_responde`: `ollama:bge-m3` o
   `cloudflare:@cf/baai/bge-m3`); lo común es solo lo que se guarda y se compara.
4. **Migración `c7a2d4e8f613`** pasa los trozos ya guardados con cualquiera de los dos identificadores al común. Al
   bajar, quedan como `ollama:bge-m3`: no queda registro de qué proveedor los embebió.

## Riesgos

- Si Cloudflare cambia los pesos de `@cf/baai/bge-m3` sin cambiar el nombre, los vectores dejarían de coincidir sin
  aviso. Se detecta corriendo `scripts/benchmark.py`; conviene correrlo antes de cambiar `EMBEDDINGS_PROVIDER`.
- Pendiente (tarea 1.9): latencia en el Mac Mini y los 89 documentos en una noche.
