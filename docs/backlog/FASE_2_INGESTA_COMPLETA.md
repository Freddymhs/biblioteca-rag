# FASE 2: INGESTA COMPLETA

**Prioridad**: Media · **Dependencias**: FASE_1 · = F2 de `_CONCEPTO.md`

## Tareas

- [x] **2.1 Páginas escaneadas**: modelo de visión (verificar si el plan MiniMax acepta imágenes; si no, proveedor configurable).
  > 2026-11-16: proveedor configurable `VISION_PROVIDER` (Ollama `moondream`). Páginas en blanco (medidas por tinta) no van al modelo. Si MiniMax acepta imágenes queda sin verificar: no se usa su llave.
- [x] **2.2 Ingesta en segundo plano**: Redis + arq; avance consultable por endpoint.
  > 2026-11-16: `POST …/lotes` (202) + `GET /api/trabajos/{id}`; worker `arq app.worker.WorkerSettings`. Probado con Redis real (testcontainers) y dentro de Docker.
- [ ] **2.3 Colección `sobre-mi`** (privada): conector HTTP a `fmarcosdev.api.resume`, re-sync manual o programado.
  > BLOQUEADA 2026-11-16: falta de Freddy la URL de la API de resume (`RESUME_API_URL`) y su visto bueno para sincronizar contra ella. Hecho: conector (contrato leído del código de esa API), sincronización con altas/cambios/bajas, trabajo en segundo plano, endpoint y CLI, probados con dobles.
- [x] **2.4 Re-embed**: script que re-vectoriza desde el texto guardado, al cambiar modelo o troceo.
  > 2026-11-16: `python -m app.cli.reembeber` (`--retrocear` usa el DoclingDocument guardado en `documento.estructura`). Un documento por transacción.

Sumadas el 2026-11-16 por la sesión supervisora (auditoría `AUDITORIA_2026-11-16.md`, parte B, y prueba en Docker):

- [x] **2.B4 Docling entre hilos**: conversión y troceo serializados con un candado (`app/services/extraccion.py`).
- [x] **2.B2 Cambio de proveedor**: re-embed como salida, y aviso explícito cuando la colección está embebida con otro modelo.
- [x] **2.B3 HNSW con filtros**: medir con datos; evaluar `hnsw.iterative_scan`.
  > 2026-11-16: medido con `scripts/medir_hnsw.py`; hoy el plan es exacto (sin riesgo); `iterative_scan` no corrige el caso con JOIN, no se aplica. Corrección de esquema propuesta en `../decisions/DECISION_HNSW_FILTROS.md` (decide Freddy).
- [x] **2.D Ollama desde Docker**: la API en compose no alcanza al Ollama del host (escucha en 127.0.0.1). Arreglar sin tocar el host y probar de punta a punta dentro de Docker.

## Criterios de Aceptación

- [ ] Las páginas sin texto de `agricultura` quedan buscables. Medido el 2026-11-15: ya no hay ningún PDF escaneado
  entero; 19 PDF tienen páginas sueltas sin texto (figuras o tablas como imagen). Detalle en `../RETOMAR.md` §6.
  > Sin cerrar 2026-11-16: el camino está hecho y probado con 2 PDF reales (Villagomez: portada descrita; FAO Bulletin16: página en blanco descartada) y dentro de Docker. Falta ingerir los 19 PDF afectados del corpus completo (horas de CPU con Docling y moondream; con el corpus completo, en el Mac Mini o aquí con su visto bueno).
- [x] Subir una carpeta no bloquea la API y su avance se puede consultar.
- [x] Re-embed no mezcla vectores de dos modelos en una búsqueda.
