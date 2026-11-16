# Diagramas de Componentes (Flowcharts)

Propósito: mapa estable del sistema. Actualizar solo si cambia la topología.

## Contexto (alto nivel)

```mermaid
flowchart LR
  persona[Persona / Swagger] --> api
  agente[Agente vía MCP · FASE_4] --> api
  admin[Freddy · API key] --> api
  api[API FastAPI] --> pg[(Postgres + pgvector)]
  api --> cf[Cloudflare Workers AI · bge-m3]
  api -.respaldo.-> ollama[Ollama local · bge-m3]
  api --> minimax[MiniMax · respuesta redactada]
  api --> redis[(Redis + arq · FASE_2)]
```

## Componentes principales

```mermaid
flowchart TB
  subgraph entrada[Entrada]
    rest[Routers REST]
    cli[CLI ingestar]
    mcp[Servidor MCP · FASE_4]
  end
  subgraph servicios[Servicios]
    det[Detección tipo + hash]
    ext[Extracción Docling + HybridChunker]
    emb[Embeddings · interfaz LangChain]
    preg[Pregunta: búsqueda + cita / «no lo sé»]
  end
  subgraph infra[Infra · Docker Compose en Mac Mini]
    pg[(Postgres + pgvector · HNSW · RLS FASE_4)]
    redis[(Redis · FASE_2)]
  end
  rest --> det --> ext --> emb --> pg
  cli --> det
  rest --> preg
  mcp --> preg
  preg --> emb
  preg --> pg
```
