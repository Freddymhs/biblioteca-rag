# RETOMAR — traspaso para construir biblioteca-rag

Escrito el 2026-11-15 por la sesión que revalidó el ecosistema completo. Todo lo de este archivo se comprobó ese día
contra el código y contra lo que corre; donde algo no se comprobó, lo dice.

## 1. Qué te toca

Construir este repo siguiendo `docs/backlog/` (34 tareas, FASE_0 a FASE_5). El avance vigente está en
`docs/backlog/README.md`; cada fase cerrada deja su `docs/backlog/INFORME_FASE_N.md`.

Lee, en este orden, antes de escribir nada:

1. `CLAUDE.md` (reglas del proyecto) y este archivo.
2. `docs/_CONCEPTO.md` (qué es, modelo de dominio, stack y por qué).
3. `docs/decisions/DECISION_SERVICIO_PUBLICO.md` (cambia el concepto: servicio público y MCP público).
4. `docs/backlog/README.md`, `FASE_0_BASE.md` y `FASE_1_MOTOR_CON_CITA.md`.
5. `docs/diagrams/DIAGRAMAS_COMPONENTES.md` y `.claude/backlog-context.json`.

Si el concepto y la decisión se contradicen, gana la decisión (es posterior).

## 2. Cómo se trabaja en esta corrida

**No empieces hasta que Freddy escriba «comienza».** Al recibirlo, haces la FASE_0 completa.

- **Implementas tú.** Este proyecto es asistido por IA (lo dice el banner del `README.md`). No uses
  `/work:backlog:next`: ese comando es modo guía, no solución. Lee el archivo de la fase y ejecuta sus tareas en el
  «Orden de ejecución» que declara.
- **Después de cada tarea:** corre tests, lint y tipos; si pasan, marca su casilla en el `FASE_N_*.md`.
- **Al cerrar una fase:** actualiza los conteos de `docs/backlog/README.md` y `.claude/backlog-progress.json`
  (el `FASE_N_*.md` manda sobre los otros dos). Luego **te detienes**, y entregas:
  1. qué quedó hecho y cómo lo verificaste (comando y resultado);
  2. los archivos tocados en orden de importancia, con qué líneas mirar y por qué;
  3. lo que no pudiste verificar y las preguntas para Freddy.
  Esperas su «sigue» para la fase siguiente.
- **Sin commits, sin `git add`, sin push.** El `.claude/settings.json` los permite porque viene de la plantilla; no
  se usan. Freddy sella con `/work:sellar:run` cuando quiere.
- **Pide confirmación antes de:** instalar herramientas de sistema, bajar modelos (`ollama pull`), correr
  migraciones contra una base que no sea un contenedor de test desechable, cualquier acción en el Mac Mini,
  exponer algo a internet, tocar `resume.json` o cualquier otro repo. Instalar dependencias del proyecto con
  `uv sync` es parte de la tarea 0.1 y no necesita pregunta.
- **Antes de usar una librería, lee su documentación actual** (MCP `context7`). El concepto es del 2026-09-27 y
  estas librerías cambian rápido: `langchain-postgres`, Docling, pgvector, testcontainers.
- **Verificación:** haz fallar cada chequeo a propósito una vez antes de creerle al verde, e imprime sobre cuántos
  casos corrió.
- **Secretos:** van solo en `.env` (ya está en `.gitignore`). Nunca imprimas un valor en el chat.

## 2.1 Orden de Freddy del 2026-11-16 (reemplaza lo que contradiga de la sección 2)

Freddy se fue a dormir y pidió terminar el proyecto sin esperarlo. Dijo, textual: «cada vez después de una fase, se
ejecuta el comando stagear el repo, y luego se sella, y luego se pushea, y luego se avanza con la siguiente fase».

**Ciclo por fase, sin esperar «sigue»:**

1. Terminar todas las tareas de la fase que se puedan hacer aquí. Tests, lint y tipos en verde.
2. Una tarea que dependa de algo que solo Freddy tiene **no detiene la fase**: se deja su casilla sin marcar, con una
   línea debajo `> BLOQUEADA 2026-11-16: falta <qué> de Freddy`, y se sigue.
3. Actualizar conteos (`docs/backlog/README.md`, `.claude/backlog-progress.json`).
4. **Stagear** los archivos de la fase, uno por uno con `git add -- <ruta>` (nunca `git add .` ni `-A`). La primera
   vez entran también `docs/backlog/`, `docs/decisions/`, `docs/diagrams/`, `docs/flows.md`, `docs/RETOMAR.md` y
   `.claude/backlog-*.json`, que nunca se commitearon. Jamás `.env`, `test.db`, `__pycache__` ni cachés.
5. **Sellar:** `Skill work:sellar:run`. Si da `🔴 PROPIO` o `⛔ BLOQUEADO`, se arregla el código y se repite. Si da
   `🅰️ PROPUESTAS`, se elige la opción más conservadora y se anota cuál y por qué en el informe de la fase.
   Si `commit:run` da `🚨 CRÍTICO` (una credencial en el diff): **no se commitea ni se pushea**; se saca la
   credencial y se repite.
6. **Commit** con el mensaje que dejó el sellado: `git commit -F <archivo .txt>`. El mensaje no lleva ninguna firma de
   herramienta ni de asistente (regla global de Freddy, `~/.claude/CLAUDE.md` §1, que trae el chequeo exacto). Un
   commit por fase.
7. **Push:** `git push origin master`.
8. Dejar el informe de la fase en `docs/backlog/INFORME_FASE_N.md` (qué se hizo, cómo se verificó, archivos por
   importancia, tareas bloqueadas, decisiones tomadas sin Freddy) y **seguir con la fase siguiente**.

**Lo que sí queda autorizado esta noche:**
- `ollama pull bge-m3` en esta máquina, para tener embeddings reales sin el token de Cloudflare.
- Usar un modelo de Ollama local como LLM para la prueba de punta a punta (ya están `qwen3:4b` y otros). MiniMax
  sigue siendo el proveedor por defecto en la configuración, pero **no se usa su llave real** hasta que Freddy
  confirme los términos del plan.
- Migraciones contra la base local de `docker compose` de este repo.

**Lo que sigue sin hacerse hasta que Freddy lo diga (se marca BLOQUEADA):**
- Todo lo que necesite el token o el account id de Cloudflare.
- Cualquier acción en el Mac Mini (benchmark de la tarea 1.9, despliegue).
- Exponer el servicio a internet (tarea 4.8) y decidir qué documentos son públicos (tarea 4.6: se puede dejar la
  tabla de licencias armada, pero el veredicto es suyo).
- Tocar otros repos o `resume.json`.

## 3. Estado verificado

**Punto de partida (2026-11-15):** 1 commit, la plantilla `template-fastapi` con el CRUD de ejemplo `items`,
`postgres:16-alpine` sin vectores y ninguna dependencia de RAG. 0 de 34 tareas.

**Al 2026-11-16:** FASE_0 completa (7/7) y FASE_1 en 9/10, con la 1.9 bloqueada. Verificado ese día por una sesión
distinta a la que escribió el código: `make check` pasa (ruff y pyright sin errores, 57 tests pasan y 7 se saltan;
esos 7 son las preguntas de oro, que solo corren contra una API viva).

- Qué se hizo y qué se decidió sin Freddy: `docs/backlog/INFORME_FASE_0.md` e `INFORME_FASE_1.md`.
- No está desplegado en ningún lado.
- El control de permisos de la sesión que construye bloquea `git add`, `git commit` y migrar la base de
  `docker compose`. El stage, el sellado, el commit y el push los hace la sesión que supervisa.

## 4. Esta máquina (ThinkPad, Linux)

- Python 3.12.3, uv 0.12.13, Docker 29.8 corriendo, Compose v2.40, ruff, pyright y `pdftotext` instalados.
- 16 núcleos, 31 GB de RAM, 167 GB libres. Sin GPU.
- Puertos 5432, 8000 y 6379 libres.
- **Tope de memoria:** tu sesión corre dentro de un scope de systemd con `MemoryMax=12G` (lo pone `~/bin/llm`).
  Todo proceso que lances desde tu shell cuenta contra ese tope; si lo supera, el sistema mata la sesión entera.
  Docling con PDFs grandes puede hacerlo. Prueba con PDFs chicos y corre la ingesta pesada dentro de un contenedor.

## 5. Llaves y proveedores

- **MiniMax:** existe `MINIMAX_PLAN_SECRET` en `~/.zsh_secrets`. El concepto usa el endpoint compatible con Anthropic
  `https://api.minimax.io/anthropic`. Sin verificar: si los términos del plan permiten usar la llave en una app propia.
- **Cloudflare Workers AI:** no hay token ni account id en `~/.zsh_secrets`. Cuando llegues a la tarea 1.4, pídeselos
  a Freddy. Hasta entonces puedes construir y testear contra la interfaz `Embeddings` con un doble.
- **Ollama:** instalado aquí y en el Mac Mini, pero **ninguno tiene `bge-m3`**. Bajarlo requiere su confirmación.
- La cuota gratis de Cloudflare que cita el concepto (2026-09-26) no se revalidó.

## 6. El corpus

Ruta: `/home/fmarcosdev/Volumes/Extended/github/PRODUCTION/BIBLIOTECAPARARAG-AGRICULTURA/`. **Solo lectura:** no
renombres, muevas ni borres nada ahí.

- **89 documentos** desde el 2026-11-15: 88 PDF reales y 1 `.txt` (`Manejo cultivo integrado maracuya.txt`). Ese día se
  sacó `crop management 1989-1990.pdf` (bitácora italiana sin conocimiento aprovechable). Donde el backlog diga «los 90
  documentos» (tarea 1.9), son 89.
- **4 PDF no tienen extensión:** `Boletín INIA N° 259`, `Boletín INIA N° 355`, `Boletín INIA N° 384` e
  `Informativo INIA N° 91`. Son el caso de prueba de la tarea 1.2 (detectar por contenido).
- **3 archivos de control que no se ingieren:** `catalogo.json`, `prompt.txt`, `LIBROS_POR_REBUSCAR.md`.
- Los más pesados: guía de pitahaya de Amazonas (84 MB), manual de poscosecha de pitahaya (73 MB),
  `Mamamani_et-al_2024_descriptores_tuna.pdf` (43 MB), `Boletín INIA N° 149.pdf` (21 MB).
- El backlog habla de 5 PDF escaneados. **Medido el 2026-11-15 con `pdftotext`:** el único escaneado entero era el
  documento que se sacó, así que hoy no queda ninguno. 19 PDF tienen páginas sueltas sin texto (figuras o tablas como imagen); los
  más afectados: `Guía Técnica del Cultivo de Olivo en la Región Tacna.pdf` (22 de 91),
  `FAO-Fruit-trees-vines-Fereres.pdf` (20 de 189), el de maracuyá «Fortalecimiento de capacidades…» (14 de 58) y el
  manual de poscosecha de pitahaya (12 de 62). El criterio de FASE_2 («los 5 PDF escaneados») hay que reescribirlo.
- `catalogo.json` se ordenó ese mismo día: quedan 9 entradas sin año (antes 12) y los cultivos pasaron de 75 a 57
  valores distintos, y después a 47 al unificar por especie (la vid se separa por destino: `vid`, `uva de mesa`,
  `uva vinífera`, `vid pisquera`). Calza 89 a 89.
- `catalogo.json` tiene una entrada curada por documento (título real, fuente, año, región, relevancia, temas,
  cultivos). Calza uno a uno con el disco. El backlog no lo usa. Si sirve para las citas (título en vez de nombre de
  archivo), propónselo a Freddy; no lo decidas tú.

## 7. El ecosistema alrededor

- **Consumidor previsto: el portal de AgriPlan** (`agriplan-portal-next`, Next.js). Freddy lo escribe a mano y
  consumirá esta API por REST. **Ningún agente toca ese repo.**
- La conexión portal ↔ este motor no está diseñada en ningún documento. No la inventes: es decisión de Freddy (§9).
- **No confundir con la otra «biblioteca»:** la API NestJS de AgriPlan ya tiene `GET /api/v1/biblioteca`, un índice
  de publicaciones de INIA (título, resumen, link). No lee PDFs. Es otro servicio y no se duplica aquí.
- **Lección de hoy para tu contrato:** el portal tiene tipos escritos que no calzan con lo que esa API devuelve,
  porque se supusieron en vez de leerse. Aquí el OpenAPI que genera FastAPI es el contrato: mantenlo exacto, no
  cambies la forma de una respuesta en silencio y deja en `docs/flows.md` el cuerpo literal de cada respuesta.
- Por defecto usa el formato nativo de FastAPI. La API NestJS envuelve todo en `{statusCode, data, meta}`; si
  conviene igualarlo es pregunta para Freddy al cerrar la FASE_1.

## 8. El Mac Mini (para FASE_1.9 y FASE_4; nada de esto sin su visto bueno)

- Apple M1 con **8 GB de RAM** y 50 GB libres, y ya corre 22 contenedores. El concepto pide que la ingesta completa
  y el benchmark corran ahí; con esa memoria puede no alcanzar. Si no alcanza, repórtalo; no lo fuerces.
- Puertos ocupados: 3002 a 3013, 4300 a 4302, 5000, 5678, 7000, 8123, 11434 (Ollama), 54321 y 54322. Libres: 8000 y 5432.
- Patrón de despliegue que ya usa `agriplan-api`: GitHub Actions con runner propio (`[self-hosted, mac-mini]`),
  `docker compose -p <nombre> -f docker-compose.prod.yml up --build -d`, y el `.env` copiado desde `~/apps/<app>/`.
- Ya existe un túnel de Cloudflare (`cloudflared tunnel run mac-mini`) con varios servicios bajo `fmarcos.dev`.
  La tarea 4.8 sería una entrada más en `~/.cloudflared/config.yml`.

## 9. Decisiones abiertas de Freddy (pregunta cuando llegues, no supongas)

1. ¿El chat del portal consultará este motor? Si sí, define qué endpoints públicos necesita primero (4.3 y 4.4).
2. ¿El MCP público (4.7) se hace dentro de la FASE_4 como dice el backlog, o después de que el portal funcione?
3. ¿Las respuestas llevan el mismo envoltorio que la API NestJS? (ver §7)
4. ¿`catalogo.json` entra como metadatos de los documentos? (ver §6)
5. Licencias de los documentos (4.6): nada se publica sin revisarlas.
