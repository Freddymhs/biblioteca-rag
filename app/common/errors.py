from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common.logger import logger


class AppError(Exception):
    """Error de dominio con su código HTTP. Los servicios lo lanzan; `main.py` lo traduce."""

    def __init__(self, status_code: HTTPStatus, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def not_found(resource: str) -> AppError:
    return AppError(HTTPStatus.NOT_FOUND, f"{resource} no existe")


def bad_request(message: str) -> AppError:
    return AppError(HTTPStatus.BAD_REQUEST, message)


def conflict(message: str) -> AppError:
    return AppError(HTTPStatus.CONFLICT, message)


def payload_too_large(message: str) -> AppError:
    return AppError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, message)


def unprocessable(message: str) -> AppError:
    return AppError(HTTPStatus.UNPROCESSABLE_ENTITY, message)


def service_unavailable(message: str) -> AppError:
    return AppError(HTTPStatus.SERVICE_UNAVAILABLE, message)


class ErrorProveedor(RuntimeError):
    """Un proveedor externo (embeddings, LLM) falló o respondió algo inválido: 502."""


# ── FastAPI exception handlers ────────────────────────────────────────────────


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def provider_error_handler(_request: Request, exc: ErrorProveedor) -> JSONResponse:
    logger.error(f"Proveedor externo: {exc}")
    return JSONResponse(status_code=HTTPStatus.BAD_GATEWAY, content={"error": str(exc)})


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if not errors:
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={"error": "Error de validación"}
        )
    first_error = errors[0]
    field = " → ".join(str(loc) for loc in first_error["loc"])
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"error": f"{field}: {first_error['msg']}"},
    )
