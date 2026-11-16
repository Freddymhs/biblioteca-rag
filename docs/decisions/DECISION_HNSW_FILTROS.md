# DECISION: búsqueda con filtros y el índice HNSW (auditoría B3)

**Fecha**: 2026-11-16 · **Estado**: medido; corrección de esquema propuesta, pendiente de Freddy

## Contexto

`buscar` filtra por espacio, colección y modelo (JOINs) y ordena por distancia coseno. pgvector
filtra *después* de recorrer el índice HNSW: si el planificador usa el índice y los vecinos más
cercanos son de otro espacio, pueden volver menos de 5 trozos y salir un «no lo sé» falso.

## Medición (`scripts/medir_hnsw.py`, reproducible)

Base desechable con los 63 trozos reales de la base de compose (bge-m3) en un espacio, 20.000
vectores de ruido en otro espacio y 3 preguntas reales. El ruido son copias perturbadas de los
trozos reales (coseno ≈ 0,85): otra colección del mismo tema. Con vectores al azar el ruido no
compite nunca (a 1.024 dimensiones queda a distancia ≈ 1) y la medición no distingue nada.

| Modo | ¿Usa HNSW? | Trozos devueltos (de 5) · recall@5 contra el exacto |
|---|---|---|
| Consulta tal cual | no: filtra y ordena exacto | 5 · 1,00 en las 3 preguntas |
| Índice forzado (`enable_seqscan`, `enable_sort` off) | sí | 1 · 0,20 en 1 de 3 preguntas (en otra corrida, 2 de 3) |
| + `hnsw.iterative_scan = strict_order` | sí | igual: 1 · 0,20 |
| + `relaxed_order`, `max_scan_tuples = 1.000.000` | sí | igual |
| + `scan_mem_multiplier = 64` | sí | igual |
| `hnsw.ef_search = 400` | sí | igual |

## Decisión

1. **Hoy no hay riesgo**: con este volumen el planificador hace búsqueda exacta sobre lo filtrado.
2. **No se aplica `iterative_scan`**: medido, no corrige el caso con filtros que llegan por JOIN.
   Sería configuración que parece proteger y no protege.
3. **Corrección propuesta (cambio de esquema, decide Freddy)**: que el filtro esté en la tabla del
   índice: `trozo.espacio_id` y `trozo.coleccion_id` (desnormalizados, con FK) o índices HNSW
   parciales por espacio. Volver a correr `scripts/medir_hnsw.py` antes y después.
4. **Cuándo revisarlo**: al cargar el corpus completo y cada vez que un espacio pase de unos miles
   de trozos (el plan cambia solo; `EXPLAIN` en el script lo muestra).
