# template-fastapi — Elevator Pitch

## ENGLISH

**Context:** A production-grade FastAPI starter for developers coming from Node/Express. The goal isn't just "a working CRUD" — it's a reference architecture that teaches Python backend patterns through running, testable code. The analogies are explicit: `pydantic-settings` ≈ Joi, `SQLAlchemy` ≈ Prisma, `Pydantic schemas` ≈ Zod, `Depends(get_db)` ≈ DI middleware.

**The Decision:** Five-layer separation — config, models, schemas, services, routers — instead of a flat Express-style structure. The trade-off: more files upfront, zero confusion about where logic lives as the project grows. Each layer has one job: models describe the database, schemas describe the API contract, services hold business logic, routers are thin HTTP wiring.

**One Real Challenge:** Where should HTTP concerns live? The answer here is: only in `main.py`. Services raise typed `AppError` domain exceptions with factory constructors (`not_found()`, `bad_request()`). Two global handlers in the entry point translate those to `JSONResponse`. Business logic never imports FastAPI response types — it speaks domain language, not HTTP language. That boundary is the template's most transferable pattern.

**Why It's Production-Ready:**
- 9 pytest tests covering full CRUD + validation errors, running against SQLite in-memory — no Postgres required to verify correctness.
- Pydantic enforces type contracts at the API boundary at both parse time and runtime; `pydantic-settings` fails fast at startup if required env vars are missing.
- loguru structured logger with `{time} | {level} | {name}:{line} | {message}` format, level configurable from env, colorized in dev.

**The Insight:** A starter template is only useful if its patterns survive the first feature addition. This one separates HTTP, persistence, and domain logic so cleanly that extending it — add a model, add schemas, add a service, add a router — never requires touching existing layers.

---

## ESPAÑOL

**Contexto:** Un starter de FastAPI listo para producción, pensado para developers que vienen de Node/Express. El objetivo no es "un CRUD que funciona" — es una arquitectura de referencia que enseña patrones de backend Python a través de código ejecutable y testeable. Las analogías están explícitas: `pydantic-settings` ≈ Joi, `SQLAlchemy` ≈ Prisma, `Pydantic schemas` ≈ Zod, `Depends(get_db)` ≈ middleware de inyección de dependencias.

**La Decisión:** Separación en cinco capas — config, models, schemas, services, routers — en lugar de una estructura plana al estilo Express. El trade-off: más archivos desde el inicio, cero confusión sobre dónde vive la lógica cuando el proyecto crece. Cada capa tiene una responsabilidad: los models describen la base de datos, los schemas describen el contrato de la API, los services contienen la lógica de negocio, y los routers son el cableado HTTP delgado.

**Un Desafío Real:** ¿Dónde deben vivir las preocupaciones HTTP? La respuesta aquí es: solo en `main.py`. Los services lanzan excepciones de dominio tipadas `AppError` con constructores semánticos (`not_found()`, `bad_request()`). Dos handlers globales en el entry point las traducen a `JSONResponse`. La lógica de negocio nunca importa tipos de respuesta de FastAPI — habla lenguaje de dominio, no lenguaje HTTP. Ese límite es el patrón más transferible de este template.

**Por Qué Está Listo para Producción:**
- 9 tests con pytest cubriendo CRUD completo + errores de validación, corriendo contra SQLite en memoria — no se necesita Postgres para verificar correctitud.
- Pydantic impone contratos de tipos en el boundary de la API en tiempo de parseo y en runtime; `pydantic-settings` falla rápido al inicio si faltan variables de entorno requeridas.
- Logger estructurado con loguru en formato `{time} | {level} | {name}:{line} | {message}`, nivel configurable desde env, colorizado en desarrollo.

**El Insight:** Un template solo es útil si sus patrones sobreviven la primera feature adicional. Este separa HTTP, persistencia y lógica de dominio con tanta claridad que extenderlo — agregar un model, schemas, un service, un router — nunca requiere tocar las capas existentes.
