# Pendientes para Freddy — 2026-11-16

Lo que quedó abierto al cerrar las cinco fases. Cada punto se lee solo y termina en una pregunta. Nada de esta
lista está resuelto.

Estado del código ese día: 31 de 34 tareas, 357 tests pasan y 7 se saltan, cinco commits en `origin/master`
(`3685baf` … `5801aa1`). Nada está desplegado ni expuesto, y ningún documento es público.

## A. Tres tareas bloqueadas: falta algo que solo tú tienes

1. **Tarea 1.9, benchmark.** Compara los embeddings de Ollama con los de Cloudflare y mide tiempos en el Mac Mini.
   Está escrito `scripts/benchmark.py`. Falta el token y el account id de Cloudflare Workers AI, que no existen en
   `~/.zsh_secrets`, y tu permiso para correr en el Mac Mini. Riesgo conocido: el Mac Mini tiene 8 GB de RAM y ya
   corre 22 contenedores. ¿Creas el token de Cloudflare y autorizas la prueba en el Mac Mini?
2. **Tarea 2.3, colección `sobre-mi`.** El conector y la sincronización están hechos y probados con dobles. Falta
   la URL de tu API de resume (`RESUME_API_URL`) y tu visto bueno para la primera sincronización real. ¿Cuál es la
   URL y la autorizas?
3. **Tarea 4.8, exposición a internet.** Están escritos `docker-compose.prod.yml` y `docs/DESPLIEGUE_PUBLICO.md`;
   no se ejecutó nada. Falta el dominio, el token del túnel y tu orden de exponer. ¿Qué dominio usas y cuándo?

## B. Decisiones de producto

4. **Qué documentos se publican.** `LICENCIAS_AGRICULTURA_2026-11-16.md` clasifica los 89: 51 sin declaración, 10
   Creative Commons, 10 «todos los derechos reservados», 10 «reproducción permitida citando la fuente», 7 solo con
   ©, 1 FAO no comercial. Hoy ninguno es público. ¿Basta «citando la fuente»? ¿Qué se hace con los de derechos
   reservados, los no comerciales y los 51 sin declaración?
5. **La llave de MiniMax.** El motor está configurado para redactar con MiniMax, pero todo se probó con un modelo
   local de Ollama: tu llave real no se usó. No se verificó si los términos de tu plan permiten usarla en una app
   propia. Con el modelo local pasan 6 de 7 preguntas de oro. ¿Confirmas los términos y habilito la llave?
6. **El chat del portal de AgriPlan.** No está diseñado en ningún lado si el portal consulta este motor. El motor ya
   ofrece `GET /api/publico/buscar` y `POST /api/publico/preguntas`, documentados en `docs/flows.md`. ¿El chat del
   portal los va a usar?
7. **Título real en las citas.** Hoy una cita muestra el nombre del archivo (`NR32257.pdf`). `catalogo.json`, en la
   carpeta del corpus, tiene el título curado de cada documento. ¿Se carga como metadatos?
8. **Respuestas sin referencia.** Si el modelo responde sin citar ningún `[n]`, la API devuelve todos los fragmentos
   consultados como citas (punto B1 de `AUDITORIA_2026-11-16.md`). ¿Se exige al menos una referencia válida para dar
   la respuesta por buena?
9. **Búsqueda con muchos datos.** Con miles de trozos y otra colección de tema parecido, la búsqueda puede devolver
   1 de 5 resultados; afecta también a lo público. Hoy no ocurre. La corrección es un cambio de esquema, medido y
   propuesto en `docs/decisions/DECISION_HNSW_FILTROS.md`. ¿Se aplica ahora o cuando el corpus lo pida?
10. **Páginas sin texto de `agricultura`.** El camino con visión está probado con dos PDF reales. Ingerir los 19
    afectados son horas de procesador. ¿Se corre en el ThinkPad o en el Mac Mini?
11. **`/docs` en producción.** La documentación interactiva describe también las rutas de administración. ¿Queda
    visible?
12. **Límites de uso público.** Por defecto: 30 búsquedas y 5 respuestas por minuto por IP, y 200 respuestas al día
    en total. ¿Sirven?
13. **Paquete `facturas`.** Es el ejemplo de referencia. ¿Refleja las facturas que te interesan (chilenas: folio,
    RUT, neto, IVA)? ¿Hace falta confirmar por lotes?
14. **Trazas.** Jaeger las guarda en memoria y se pierden al reiniciarlo. ¿Alcanza, o quieres historia persistente?
    ¿Basta `GET /api/uso` o quieres un tablero?

## C. Riesgos anotados por las auditorías, sin corregir

Cada auditoría separó lo que se corrigió antes de su commit de lo que quedó abierto. Lo abierto está en:

- `AUDITORIA_2026-11-16.md`, parte B: B8 (un `.txt` que contenga `%PDF-` se clasifica como PDF) y B9 (tests que
  faltan). Los demás se resolvieron en fases posteriores.
- `AUDITORIA_FASE_2_2026-11-16.md`, parte D: D2 a D5 (el re-embed aborta entero si falla un documento, `/trabajos`
  no informa páginas sin indexar, tests que no pueden fallar).
- `AUDITORIA_FASE_3_2026-11-16.md`, parte F: F2 (el texto se trunca a 12.000 caracteres sin avisar), F3 (la salida
  estructurada solo se probó con Ollama), F5 y F6.
- `AUDITORIA_FASE_4_2026-11-16.md`, parte H, y lo no verificado: nada se probó detrás de un túnel real de Cloudflare.
- `AUDITORIA_FASE_5_2026-11-16.md`, parte J: J1 a J5.

## D. Para el portal, que escribes tú

- El contrato está en `docs/flows.md`, con el cuerpo literal de cada respuesta capturado de la API real.
- Una cita trae `pagina_inicio` y `pagina_fin`, no una sola página.
- El campo `origen` de una cita vale `texto`, `vision` o `datos`.
- Lo público no lleva clave; todo lo demás bajo `/api` lleva el encabezado de la clave.
