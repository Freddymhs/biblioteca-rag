# DECISION: el chat del portal de AgriPlan consume la API pública de este motor

**Fecha**: 2026-11-16 · **Estado**: aceptada (Freddy, punto 6 de `PENDIENTES_FREDDY_2026-11-16.md`; tarea 6.6)

## Contexto

El portal de AgriPlan (`agriplan-portal-next`, Next.js) tiene un chat. Hasta hoy no estaba escrito en ningún lado si
ese chat consulta este motor. Freddy decidió que sí, por lo público: `GET /api/publico/buscar` y
`POST /api/publico/preguntas`. El cliente lo escribe él a mano en el repo del portal; este repo no lo toca.

## Decisión

1. **El contrato es `docs/flows.md`**: secciones «Servicio público (FASE_4)» y «Para quien escribe el cliente del
   portal (FASE_6)», con cada cuerpo capturado literal de la API. Si una forma cambia, cambia ahí en el mismo commit.
2. **Sin clave.** Lo público no lleva `X-API-Key`. El portal nunca debe tener la clave: con ella se lee lo privado.
3. **El navegador llama directo**, con CORS para el origen del portal por configuración (`CORS_ORIGINS` en `.env`,
   lista JSON). El motor expone `X-Traza-Id` para que el portal pueda mostrarlo o registrarlo.
4. **Por qué el navegador y no el servidor del portal**: los límites son por IP (5 respuestas y 30 búsquedas por
   minuto; 20 respuestas y 500 búsquedas por día). Si el servidor del portal hiciera de intermediario, todos los
   visitantes compartirían su IP y el portal entero quedaría en 5 respuestas por minuto. El motor no confía en
   encabezados de reenvío que no sean `CF-Connecting-IP` detrás del túnel, a propósito (se falsificarían).
5. **Una respuesta sin cita no es una respuesta** (6.2): `sabe: false` y `citas: []`. El chat debe mostrar el «no lo
   sé» tal cual y no inventar una respuesta propia.
6. **La cita se muestra con `titulo`** (6.1), que siempre trae texto (el título real o, si no hay, el nombre del
   archivo), más `pagina_inicio`/`pagina_fin`, `fuente`, `anno` y `licencia` (obligación de atribución de varias
   licencias del corpus).

## Consecuencias

- Al exponer (tarea 4.8), poner en `.env` del Mac Mini `CORS_ORIGINS=["https://<dominio del portal>"]`.
- Si algún día el portal necesita llamar desde su servidor (p. ej. para cachear), habrá que darle un límite propio por
  clave, no por IP: es otra decisión.
- La respuesta redactada usa el LLM y puede tardar (medido con MiniMax en la tarea 6.5); el chat debe mostrar que está
  esperando y tolerar un 503 de «demasiadas respuestas en curso» reintentando más tarde.
