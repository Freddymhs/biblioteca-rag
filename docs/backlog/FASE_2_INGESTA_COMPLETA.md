# FASE 2: INGESTA COMPLETA

**Prioridad**: Media · **Dependencias**: FASE_1 · = F2 de `_CONCEPTO.md`

## Tareas

- [ ] **2.1 Páginas escaneadas**: modelo de visión (verificar si el plan MiniMax acepta imágenes; si no, proveedor configurable).
- [ ] **2.2 Ingesta en segundo plano**: Redis + arq; avance consultable por endpoint.
- [ ] **2.3 Colección `sobre-mi`** (privada): conector HTTP a `fmarcosdev.api.resume`, re-sync manual o programado.
- [ ] **2.4 Re-embed**: script que re-vectoriza desde el texto guardado, al cambiar modelo o troceo.

## Criterios de Aceptación

- [ ] Las páginas sin texto de `agricultura` quedan buscables. Medido el 2026-11-15: ya no hay ningún PDF escaneado
  entero; 19 PDF tienen páginas sueltas sin texto (figuras o tablas como imagen). Detalle en `../RETOMAR.md` §6.
- [ ] Subir una carpeta no bloquea la API y su avance se puede consultar.
- [ ] Re-embed no mezcla vectores de dos modelos en una búsqueda.
