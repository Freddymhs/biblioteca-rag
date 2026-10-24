🤖 Proyecto asistido por IA — NO se contabiliza en CV/resume (no es práctica manual real).

# biblioteca-rag

Motor RAG self-hosted con cita. Nació de `Freddymhs/template-fastapi`; el concepto vive en `docs/_CONCEPTO.md`.

Pensado para devs que vienen de Node/Express:
- `pydantic-settings` ≈ Joi (validación de env)
- `SQLAlchemy` ≈ Prisma (ORM)
- `Pydantic schemas` ≈ Zod (validación de request/response)
- `pytest` ≈ vitest / jest
- `Depends(get_db)` ≈ middleware de inyección de dependencias

---

## Setup rápido

```bash
cp .env.example .env
# Edita DATABASE_URL y SECRET_KEY en .env

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Aplica migraciones
alembic upgrade head

# Servidor de desarrollo
uvicorn main:app --reload
```

Docs interactivos en `http://localhost:8000/docs`

---

## Con Docker

```bash
docker compose up --build
```

API en `http://localhost:8000` · PostgreSQL en `localhost:5432`

---

## Estructura

```
template-fastapi/
├── main.py                  # App entry, middleware, routers
├── alembic/                 # Migraciones SQL (como prisma migrate)
│   ├── env.py
│   └── versions/
├── app/
│   ├── config/
│   │   ├── settings.py      # Variables de entorno validadas
│   │   └── database.py      # Engine + Session + Base
│   ├── common/
│   │   ├── errors.py        # AppError + handlers globales
│   │   └── logger.py        # loguru configurado
│   ├── models/
│   │   └── item.py          # SQLAlchemy model (tabla en DB)
│   ├── schemas/
│   │   └── item.py          # Pydantic schemas (request/response)
│   ├── services/
│   │   └── item_service.py  # Lógica de negocio (queries)
│   └── routers/
│       └── items.py         # Rutas HTTP (/api/items)
└── tests/
    ├── conftest.py          # SQLite in-memory para tests (sin Postgres real)
    └── test_items.py        # 9 tests cubriendo todo el CRUD
```

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/items/` | Listar todos |
| POST | `/api/items/` | Crear item |
| GET | `/api/items/:id` | Obtener por ID |
| PATCH | `/api/items/:id` | Actualizar parcialmente |
| DELETE | `/api/items/:id` | Eliminar |

---

## Tests

```bash
pytest -v
```

Los tests usan SQLite en memoria — no necesitan PostgreSQL corriendo.

---

## Migraciones (Alembic)

```bash
# Crear migración automática tras cambiar un model
alembic revision --autogenerate -m "add users table"

# Aplicar migraciones pendientes
alembic upgrade head

# Ver estado
alembic current

# Revertir último paso
alembic downgrade -1
```

---

## Cómo extender

1. Agrega un model en `app/models/`
2. Agrega schemas Pydantic en `app/schemas/`
3. Crea un service en `app/services/`
4. Registra el router en `app/routers/` e inclúyelo en `main.py`
5. Genera y aplica la migración con Alembic
