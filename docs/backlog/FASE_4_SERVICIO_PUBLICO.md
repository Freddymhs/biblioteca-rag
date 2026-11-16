# FASE 4: SERVICIO PÚBLICO

**Prioridad**: Alta · **Dependencias**: FASE_1 (no depende de 2 ni 3) · Origen: `../decisions/DECISION_SERVICIO_PUBLICO.md`

## Orden de ejecución

1. Tareas 4.1, 4.2 — separación; nada se expone antes.
2. Tareas 4.3–4.7 — dependen de 4.1.
3. Tarea 4.8 — al final.

## Tareas

- [ ] **4.1 RLS por espacio**: rol `publico` solo lee colecciones públicas; rol restringido para agentes.
- [ ] **4.2 Flags**: `coleccion.publica`, `documento.licencia`. `agricultura` pública, `sobre-mi` privada.
- [ ] **4.3 Búsqueda pública sin LLM**: fragmentos con cita (documento, página). Nunca el PDF completo.
- [ ] **4.4 Respuesta redactada con límite**: rate limit por IP + tope diario global (429).
- [ ] **4.5 Auth para escribir**: API key para subir, crear colecciones y administrar.
- [ ] **4.6 Licencias**: revisar las de los papers de `agricultura`; licencia no verificada → documento no público.
- [ ] **4.7 MCP público** (HTTP): tools `buscar` y `preguntar`; Hermes lo consume como uno más.
- [ ] **4.8 Exposición**: Cloudflare Tunnel desde el Mac Mini + dominio.

## Criterios de Aceptación

- [ ] Sin API key no se escribe (401).
- [ ] Una colección privada no aparece desde el rol público (test).
- [ ] Superar el límite devuelve 429.
- [ ] Un agente externo consulta por MCP y recibe fragmentos con cita.
