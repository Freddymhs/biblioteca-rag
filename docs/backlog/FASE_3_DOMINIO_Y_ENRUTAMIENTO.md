# FASE 3: DOMINIO Y ENRUTAMIENTO

**Prioridad**: Media · **Dependencias**: FASE_2 · = F3 de `_CONCEPTO.md`

## Orden de ejecución

1. Tarea 3.1 — contrato que 3.3 implementa.
2. Tarea 3.2 — independiente.
3. Tarea 3.3 — depende de 3.1.

## Tareas

- [x] **3.1 Paquete de dominio**: esquema Pydantic por tipo de documento → extracción estructurada → confirmación (endpoint desde el JSON Schema). Solo se embebe lo confirmado.
- [x] **3.2 Enrutamiento**: herramientas SQL fijas por colección + LangGraph clasifica «cálculo vs significado». El LLM nunca escribe SQL libre.
- [x] **3.3 Paquete `facturas`** como ejemplo de referencia.
  > 2026-11-16: probado con Ollama `llama3.2:3b`: 2 de 3 preguntas de cálculo fueron a SQL (la tercera cayó a semántica). La llamada con MiniMax queda sin probar (sin llave).

## Criterios de Aceptación

- [x] Una pregunta de cálculo usa una herramienta SQL; una de significado, búsqueda semántica.
- [x] Un dato no confirmado no queda buscable.
