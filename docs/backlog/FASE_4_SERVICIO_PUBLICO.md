# FASE 4: SERVICIO PÚBLICO

**Prioridad**: Alta · **Dependencias**: FASE_1 (no depende de 2 ni 3) · Origen: `../decisions/DECISION_SERVICIO_PUBLICO.md`

## Orden de ejecución

1. Tareas 4.1, 4.2 — separación; nada se expone antes.
2. Tareas 4.3–4.7 — dependen de 4.1.
3. Tarea 4.8 — al final.

## Tareas

- [x] **4.1 RLS por espacio**: rol `publico` solo lee colecciones públicas; rol restringido para agentes.
- [x] **4.2 Flags**: `coleccion.publica`, `documento.licencia`. `agricultura` pública, `sobre-mi` privada.
- [x] **4.3 Búsqueda pública sin LLM**: fragmentos con cita (documento, página). Nunca el PDF completo.
- [x] **4.4 Respuesta redactada con límite**: rate limit por IP + tope diario global (429).
- [x] **4.5 Auth para escribir**: API key para subir, crear colecciones y administrar.
- [x] **4.6 Licencias**: revisar las de los papers de `agricultura`; licencia no verificada → documento no público.
  > 2026-11-16: tabla de los 89 en `LICENCIAS_AGRICULTURA_2026-11-16.md`. El veredicto por documento es de Freddy;
  > hasta entonces ninguno es público.
- [x] **4.7 MCP público** (HTTP): tools `buscar` y `preguntar`; Hermes lo consume como uno más.
- [x] **4.8 Exposición**: Cloudflare Tunnel desde el Mac Mini + dominio. Hecho 2026-11-22: `https://biblioteca.fmarcos.dev`
  (ver «Despliegue vigente» en `docs/DESPLIEGUE_PUBLICO.md`).
  > BLOQUEADA 2026-11-16: falta el túnel, el dominio y la orden de exponer de Freddy. Escrito y no ejecutado:
  > `docker-compose.prod.yml` y `docs/DESPLIEGUE_PUBLICO.md`.

## Sumado a esta fase (auditorías anteriores)

- [x] **B5** Fragmentos delimitados en el prompt (el texto de un documento no es instrucción).
- [x] **B6** Contenedor: migración al arrancar, `HEALTHCHECK`, un solo proceso de uvicorn, modelos en la imagen.
- [x] **B7** `SECRET_KEY` sin uso: eliminada (la reemplaza `API_KEY`).
- [x] **D1** Subidas pesadas siempre por la cola (`POST …/documentos` responde 413 y apunta a `…/lotes`).
- [x] **D6** Redis con contraseña.
- [x] **F1** Tope de citas en un cálculo.
- [x] **F4** Un lote a una colección con paquete se rechaza de entrada (422).

## Criterios de Aceptación

- [x] Sin API key no se escribe (401).
- [x] Una colección privada no aparece desde el rol público (test).
- [x] Superar el límite devuelve 429.
- [x] Un agente externo consulta por MCP y recibe fragmentos con cita.
