# DECISION: búsqueda con filtros y el índice HNSW (auditoría B3, tarea 6.3)

**Fecha**: 2026-11-16 · **Estado**: aplicada (FASE_6, tarea 6.3, por decisión de Freddy, punto 9 de los pendientes)

## Contexto

`buscar` filtra por espacio, colección, modelo y, en lo público, por colección pública y licencia verificada, y ordena
por distancia coseno. pgvector filtra *después* de recorrer el índice HNSW: si los vecinos más cercanos son de otra
colección (u otro espacio, o privados), vuelven menos de 5 trozos y sale un «no lo sé» falso. Con el volumen de hoy el
planificador hace búsqueda exacta y no pasa; con miles de trozos parecidos en otra colección, pasaría.

Freddy pidió aplicar la corrección ahora que no hay datos, eligiendo entre desnormalizar `espacio_id`/`coleccion_id` en
`trozo` o índices parciales, medido antes y después e incluido el caso público.

## Medición (`scripts/medir_hnsw.py`, reproducible)

Base desechable: los 63 trozos reales de la base de compose (bge-m3), en una colección **pública** con licencia
verificada, y 20.000 trozos de ruido del mismo tema (copias perturbadas de los reales, coseno ≈ 0,85) en una colección
**privada** de otro espacio (o del mismo, con `--ruido-en-el-espacio`). Tres preguntas reales. Lo público se mide con el
rol `biblioteca_publico` de verdad (el RLS filtra). «Forzado» apaga `enable_seqscan` y `enable_sort` para simular lo
que hará el planificador con muchos datos: usar el índice HNSW.

```
uv run python scripts/medir_hnsw.py --revision 9c4d2e7f1a36          # antes (sin columnas)
uv run python scripts/medir_hnsw.py --revision head                  # después
uv run python scripts/medir_hnsw.py --revision head --ruido-en-el-espacio
```

Trozos devueltos (de 5) en las tres preguntas, ruido en OTRO espacio (aquí recall@5 = devueltos/5):

| Consulta | Exacta | HNSW forzado | + `iterative_scan` estricto | + relajado | + `max_scan_tuples` 1.000.000 |
|---|---|---|---|---|---|
| privada por JOIN (antes) | 5, 5, 5 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 |
| pública por JOIN + RLS (antes) | 5, 5, 5 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 |
| pública, solo el RLS de `trozo` | 5, 5, 5 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 |
| privada por `trozo.espacio_id` (desnormalizado) | 5, 5, 5 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 |
| privada con **índice HNSW parcial** `WHERE espacio_id = …` | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 |
| **privada, CTE exacta (la app desde 6.3)** | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 |
| **pública, CTE exacta + RLS (la app desde 6.3)** | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 | 5, 5, 5 |

Latencia (mediana de 5 corridas, planificador normal):

| Consulta | 63 trozos filtrados | 20.063 trozos filtrados (`--ruido-en-el-espacio`) |
|---|---|---|
| privada, CTE exacta (la app) | 1,5 ms | 134 ms |
| pública, CTE exacta + RLS (la app) | 43 ms (el RLS recorre los 20.063) | 49 ms |
| privada, índice parcial (modo forzado, el que lo usa) | 1,5 ms | 1,2–2,3 ms, pero recall 0,2–0,6 (ver abajo) |

**Con 20.000 trozos parecidos en el MISMO espacio** (`--ruido-en-el-espacio`), devolver 5 ya no basta: hay que mirar
cuáles. Recall@5 contra la exacta en las tres preguntas:

| Consulta | Exacta | HNSW forzado (también con `iterative_scan`) |
|---|---|---|
| privada por JOIN o por `trozo.espacio_id` | 1,0 · 1,0 · 1,0 | 1,0 · 0,4 · 0,2 (devuelve 5, no los correctos) |
| privada con índice HNSW parcial | 1,0 · 1,0 · 1,0 | 1,0 · 0,6 · 0,2 |
| pública (cualquier forma con índice) | 1,0 · 1,0 · 1,0 | 1 de 5 · 0,2 |
| **CTE exacta, privada y pública (la app)** | 1,0 · 1,0 · 1,0 | 1,0 · 1,0 · 1,0 |

HNSW es aproximado: con miles de vecinos casi iguales, aun sin filtro que lo estorbe, se queda con otros.

**Lo que la medición anterior no vio.** La versión previa de este ADR repetía la misma consulta muchas veces en una
conexión, y psycopg la prepara en el servidor a partir de la sexta (`prepare_threshold`): desde ahí corría el plan
preparado bajo **otro** modo (otros `SET LOCAL`) y el `EXPLAIN`, que no usa ese plan, mostraba uno distinto. Se vio al
salir 1 de 5 en una búsqueda «exacta». El script usa ahora `prepare_threshold=None` y todas las cifras de arriba son de
esa corrida.

## Decisión

1. **Se desnormaliza** `trozo.espacio_id` y `trozo.coleccion_id` (migración `b1e6f3a9d250`, con FK e índices btree). Los
   completa un trigger de la base desde el documento: ningún INSERT puede olvidarlos ni contradecirlos.
2. **Desnormalizar solo no corrige el recorrido HNSW** (medido: 1 de 5, con o sin `iterative_scan`). Por eso la búsqueda
   es **exacta por construcción**: una CTE `MATERIALIZED` calcula la distancia de cada trozo filtrado (los btree de
   `trozo` acotan cuáles) y afuera se ordena y se corta. HNSW solo sirve `ORDER BY embedding <=> v LIMIT k` directo
   sobre la tabla, y esta forma no lo es. No depende de ningún `SET` del planificador.
3. **Lo público** filtra en `trozo` por `documento_id = ANY(documentos públicos)` además del RLS; misma CTE.
4. **Índices parciales: medidos, no aplicados.** Corrigen el caso «vecinos de otro espacio» y son los más rápidos,
   pero con muchos trozos parecidos dentro del propio espacio su recall cae a 0,2–0,6 (HNSW es aproximado), solo
   sirven a lo privado (lo público cruza espacios) y exigen un índice por espacio.
5. **Cuándo revisarlo**: el costo de la exacta crece con los trozos filtrados (134 ms con 20.000). Si un espacio pasa de
   unos 100.000 trozos (≈ 0,7 s por búsqueda), se elige entre más latencia exacta o un índice parcial por espacio
   aceptando recall aproximado (punto 4), midiendo con este mismo script. Lo público, con muchos más datos,
   necesitaría además su propia marca en `trozo`.
6. **El índice HNSW general se queda**: no lo usa la búsqueda filtrada; quitarlo es otra migración y no aporta hoy.

## Medición de la auditoría K2 (2026-11-22)

La CTE de arriba unía el trozo completo (vector y texto) de **todos** los candidatos y recién después ordenaba y cortaba
en 5. Desde K2 se ordena y se corta sobre `(id, distancia)` y solo los 5 elegidos se unen con su trozo y su documento.

`scripts/medir_busqueda.py` mide la función `buscar` de la app en una base desechable: 25.000 trozos, todos en una
colección pública con licencia verificada (todos pasan el filtro: el peor caso de la exacta), texto de 2.000 caracteres
por trozo. Mediana de 75 búsquedas; las dos versiones en la misma máquina, una tras otra:

| `buscar` | privada (espacio + colección) | pública (rol `biblioteca_publico`, RLS) |
|---|---|---|
| antes de K2 | 168 ms (p90 172) | 254 ms (p90 259) |
| **desde K2** | **134 ms** (p90 136) | **142 ms** (p90 147) |

Las dos devuelven 5 en cada búsqueda. Con el corpus real (`biblioteca_rag_prod`, 11.628 trozos, pregunta embebida con
Cloudflare): **53 ms** privada y pública, mediana de 5 preguntas. El umbral del punto 5 no cambia.
