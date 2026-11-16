# Backlog — biblioteca-rag

Motor RAG con cita; primer uso: biblioteca agrícola. Concepto: `../_CONCEPTO.md`. Cambio de rumbo (servicio público): `../decisions/DECISION_SERVICIO_PUBLICO.md`.

| Fase | Archivo | Prioridad | Tareas |
|---|---|---|---|
| 0 | `FASE_0_BASE.md` | Alta | 7/7 |
| 1 | `FASE_1_MOTOR_CON_CITA.md` | Alta | 9/10 (1.9 bloqueada) |
| 2 | `FASE_2_INGESTA_COMPLETA.md` | Media | 3/4 (2.3 bloqueada) + 4/4 sumadas |
| 3 | `FASE_3_DOMINIO_Y_ENRUTAMIENTO.md` | Media | 3/3 |
| 4 | `FASE_4_SERVICIO_PUBLICO.md` | Alta | 7/8 (4.8 bloqueada) + 7/7 sumadas |
| 5 | `FASE_5_OBSERVABILIDAD.md` | Baja | 2/2 |

**Total: 31/34** (bloqueadas: 1.9, 2.3 y 4.8, por Freddy). Las fases son las F1–F5 del concepto, salvo FASE_4 (servicio público, ver la decisión).

> **Lo que espera una decisión de Freddy:** [`PENDIENTES_FREDDY_2026-11-16.md`](PENDIENTES_FREDDY_2026-11-16.md).

## Fuera de este repo

- Página web de F1 (subir, elegir colección, preguntar, ver la cita) → futuro repo `web/`. En este repo la interfaz es Swagger.

## Diagramas de Referencia

| Archivo | Tipo | Contenido |
|---|---|---|
| `../diagrams/DIAGRAMAS_COMPONENTES.md` | Flowcharts | Topología del sistema |

Referencia estable: las fases no la repiten. Se actualiza solo si cambia la topología.

## Decisiones Técnicas

`../decisions/` — `DECISION_[TEMA].md`, el porqué y no el qué.

## Validación de Flujos

| Archivo | Propósito |
|---|---|
| `../flows.md` | Flujos de uso documentados a mano. Guía para QA. |
