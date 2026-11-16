# DECISION: servicio público y gratuito

**Fecha**: 2026-10-24 · **Estado**: aceptada · **Cambia**: `_CONCEPTO.md` («self-hosted, no SaaS público»; exposición a internet fuera de v1)

## Contexto

Objetivo real (Freddy): que cualquiera consulte información técnica libre, mejor estructurada, sin pagar. El concepto lo pensaba como herramienta personal.

## Decisión

1. **Publicar es FASE_4**, antes de observabilidad. FASE_1–3 se construyen privadas.
2. **MCP público** en vez de MCP para Hermes: cualquier agente consulta; Hermes es un consumidor más.
3. **Costo**: lo público devuelve fragmentos con cita **sin LLM**. La respuesta redactada (MiniMax) tiene límite de uso.
4. **Licencias**: se publican fragmentos con cita, nunca el PDF. Papers con licencia no verificada no son públicos.
5. **Lo personal nunca es público**: separación por espacio (RLS) va en FASE_4, antes de exponer nada.

## Consecuencias

- Hace falta auth para escribir (subir, crear colecciones) y rate limit para leer.
- `coleccion` lleva flag `publica`; `documento` lleva `licencia`.
- Riesgo abierto del concepto: términos del plan MiniMax para uso en app — verificar antes de habilitar respuesta redactada pública.
