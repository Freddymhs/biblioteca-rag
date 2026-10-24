from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config.settings import settings
from app.common.errors import AppError, app_error_handler, validation_error_handler
from app.common.logger import logger
from app.routers.items import router as items_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} started — docs at /docs")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],  # set CORS_ORIGINS in .env for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ─────────────────────────────────────────────────────────

app.add_exception_handler(AppError, app_error_handler)              # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(items_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
