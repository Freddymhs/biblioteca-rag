# biblioteca-rag — Elevator Pitch

> Borrador. Se regenera desde el código con `/review:elevator_speech` al cerrar la FASE_1,
> cuando exista el motor con cita. Hasta entonces describe la intención, no lo construido.

## ESPAÑOL

**Contexto:** Un motor RAG genérico que responde con cita al documento de origen, o dice «no lo sé» cuando la
respuesta no está en los datos. Primer uso: una biblioteca agrícola de manuales y boletines técnicos.

**La decisión:** El dominio es data, no código. Espacios y colecciones viven en la base; agregar una biblioteca
nueva no requiere un fork. Los proveedores (LLM y embeddings) están detrás de interfaces de LangChain y se
cambian por configuración.

**El desafío:** Que la respuesta sea verificable. Cada trozo guarda su texto original, la página y el modelo que
lo embebió; la cita sale de un JOIN en la misma base (Postgres + pgvector), y sin contexto relevante el motor se
niega a improvisar.

## ENGLISH

**Context:** A generic RAG engine that answers with a citation to the source document, or says "I don't know"
when the answer isn't in the data. First use: an agricultural library of technical manuals and bulletins.

**The decision:** The domain is data, not code. Spaces and collections live in the database; adding a new
library never requires a fork. Providers (LLM and embeddings) sit behind LangChain interfaces and are swapped
through configuration.

**The challenge:** Making answers verifiable. Every chunk keeps its original text, page, and the model that
embedded it; the citation comes from a JOIN in the same database (Postgres + pgvector), and with no relevant
context the engine refuses to improvise.
